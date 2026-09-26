"""Run the ticket graph for one ticket and save what it produced.

Runs as a background task after a ticket is created, so it never raises: a
failure is logged and written as a `failed` event, and the ticket stays visible
at `new` for a person to handle. It changes no status — classification adds
information to a ticket, it does not move it through the lifecycle.
"""

import logging

from cms.config.settings import get_settings
from cms.db.repositories import ticket_events, tickets
from cms.rag.nodes.classify_ticket import join_complaint
from cms.rag.ticket_graph import get_ticket_graph
from cms.schemas.ticket_classification import TicketClassification

logger = logging.getLogger(__name__)


def classification_patch(result: TicketClassification) -> dict:
    """The `tickets` columns the classifier fills."""
    return {
        "predicted_dept": result.department,
        "dept_confidence": result.confidence,
        "category": result.category,
        "entities": result.entities.model_dump(exclude_none=True),
        "suggested_severity": result.suggested_severity,
        "dept_candidates": [c.model_dump() for c in result.candidates],
    }


async def _fail(ticket_id: str, stage: str, detail: dict) -> None:
    """Record why a ticket was not classified. `append_event` swallows its own failures."""
    await ticket_events.append_event(ticket_id, "failed", {"stage": stage, **detail})


async def process_ticket(ticket_id: str) -> None:
    """Guard and classify one ticket, then save the result on it."""
    stage = "fetch"
    try:
        row = await tickets.fetch_ticket(ticket_id)

        stage = "ticket_graph"
        state = await get_ticket_graph().ainvoke(
            {"ticket_id": ticket_id, "query": join_complaint(row["subject"], row.get("body"))}
        )

        if state.get("input_blocked"):
            logger.warning("Ticket %s blocked by the input guard: %s", ticket_id, state.get("guard_reasons"))
            await _fail(ticket_id, "input_guard", {"reasons": state.get("guard_reasons", [])})
            return

        stage = "save"
        result: TicketClassification = state["classification"]
        await tickets.update_ticket(ticket_id, classification_patch(result))
    except Exception as exc:
        logger.exception("Ticket %s: processing failed at stage %s", ticket_id, stage)
        await _fail(ticket_id, stage, {"error": f"{type(exc).__name__}: {exc}"})
        return

    settings = get_settings()
    await ticket_events.append_event(
        ticket_id,
        "classified",
        {
            "candidates": [c.model_dump() for c in result.candidates],
            "suggested_severity": result.suggested_severity,
            "category": result.category,
            "reason": result.reason,
            "model": settings.openrouter_model_cheap,
            "prompt_version": settings.classify_ticket_prompt_version,
        },
    )
    logger.info("Ticket %s classified: %s (%.2f)", ticket_id, result.department, result.confidence)
