"""Run the ticket graph for one ticket and save what it produced.

Runs as a background task after a ticket is created, so it never raises: a
failure is logged and written as a `failed` event, and the ticket stays visible
for a person to handle. The classification and the draft are saved separately,
so one failing never loses the other.

The ticket moves `processing` → `drafted` | `needs_review` | `processing_failed`;
`ticket_gate.review_reasons` decides between the first two.
"""

import logging
from uuid import UUID, uuid4

from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.db.repositories import drafts, ticket_events, tickets
from cms.rag.context import build_generation_context
from cms.rag.nodes.classify_ticket import join_complaint
from cms.rag.ticket_graph import DRAFT_REPLY, get_ticket_graph
from cms.rag.ticket_state import TicketState
from cms.schemas.generation import Citation
from cms.schemas.ticket_classification import TicketClassification
from cms.services import ticket_service
from cms.services.ticket_gate import review_reasons

logger = logging.getLogger(__name__)

# The label `build_case_text` puts before a case's resolution. A case is one chunk.
RESOLUTION_LABEL = "RESOLUTION:"


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


def case_resolution(text: str) -> str | None:
    """The resolution section of a case chunk, or None if it has none."""
    _, found, resolution = text.partition(RESOLUTION_LABEL)
    return (resolution.strip() or None) if found else None


def _evidence_row(citation: Citation, score: float, cited: set[int], id_key: str) -> dict:
    return {
        "marker": citation.marker,
        "chunk_id": citation.chunk_id,
        id_key: citation.doc_id,
        "title": citation.title,
        "snippet": citation.snippet,
        "score": float(score),
        "cited": citation.marker in cited,
    }


def evidence_rows(
    policy_hits: list[tuple[Document, float]],
    case_hits: list[tuple[Document, float]],
    cited: list[Citation],
) -> tuple[list[dict], list[dict]]:
    """`(retrieved_cases, policy_refs)`: every chunk the drafter was offered, with its score.

    The offered citations are rebuilt the way the drafter built them. They keep
    the hits' order and stop at the context budget, so zipping pairs each with its hit.
    """
    _, _, offered = build_generation_context(policy_hits, case_hits)
    cited_markers = {citation.marker for citation in cited}
    offered_policies = [c for c in offered if c.doc_type == "policy"]
    offered_cases = [c for c in offered if c.doc_type == "case"]

    policy_refs = [
        {**_evidence_row(citation, score, cited_markers, "policy_id"), "section": citation.section}
        for citation, (_document, score) in zip(offered_policies, policy_hits)
    ]
    retrieved_cases = [
        {
            **_evidence_row(citation, score, cited_markers, "case_id"),
            "resolution": case_resolution(document.page_content),
        }
        for citation, (document, score) in zip(offered_cases, case_hits)
    ]
    return retrieved_cases, policy_refs


async def _fail(ticket_id: str, stage: str, detail: dict) -> None:
    """Record why part of a ticket's processing failed. `append_event` swallows its own failures."""
    await ticket_events.append_event(ticket_id, "failed", {"stage": stage, **detail})


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


async def _save_classification(ticket_id: str, result: TicketClassification) -> None:
    """Write the classifier's columns on the ticket, then the `classified` event."""
    try:
        await tickets.update_ticket(ticket_id, classification_patch(result))
    except Exception as exc:
        logger.exception("Ticket %s: saving the classification failed", ticket_id)
        await _fail(ticket_id, "save_classification", {"error": _error_text(exc)})
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


async def _save_draft(ticket_id: str, state: TicketState, run_id: UUID) -> bool:
    """Add the draft as the ticket's next `customer_reply` version, then the `drafted` event.

    Returns whether the draft was saved.
    """
    settings = get_settings()
    no_match = bool(state.get("no_match"))
    model = settings.holding_reply_model if no_match else settings.openrouter_model_main
    prompt_version = (
        settings.holding_reply_prompt_version if no_match else settings.customer_reply_prompt_version
    )
    grounded = state.get("grounded")

    try:
        latest = await drafts.fetch_latest_draft(ticket_id)
        version = latest["version"] + 1 if latest else 1
        retrieved_cases, policy_refs = evidence_rows(
            state.get("policy_hits", []), state.get("case_hits", []), state.get("citations", [])
        )
        saved = await drafts.insert_draft(
            {
                "ticket_id": ticket_id,
                "version": version,
                "kind": drafts.CUSTOMER_REPLY,
                "draft_text": state["draft"],
                "retrieved_cases": retrieved_cases,
                "policy_refs": policy_refs,
                "no_match": no_match,
                "grounded": grounded,
                "guard_reasons": state.get("guard_reasons", []) if grounded is False else [],
                "model": model,
                "prompt_version": prompt_version,
                "langsmith_run_id": str(run_id),
            }
        )
    except Exception as exc:
        logger.exception("Ticket %s: saving the draft failed", ticket_id)
        await _fail(ticket_id, "save_draft", {"error": _error_text(exc)})
        return False

    await ticket_events.append_event(
        ticket_id,
        "drafted",
        {
            "draft_id": saved["id"],
            "version": version,
            "no_match": no_match,
            "grounded": grounded,
            "risk_flags": state.get("risk_flags", []),
            "model": model,
            "prompt_version": prompt_version,
        },
    )
    logger.info(
        "Ticket %s drafted: version %d, no_match=%s, grounded=%s", ticket_id, version, no_match, grounded
    )
    return True


async def _finish(ticket_id: str, status: str, reasons: list[str]) -> None:
    """Hand the outcome to the gate's status change. Never raises."""
    try:
        await ticket_service.finish_processing(ticket_id, status, reasons)
    except Exception as exc:
        logger.exception("Ticket %s: could not move it to %s", ticket_id, status)
        await _fail(ticket_id, "gate", {"error": _error_text(exc)})


async def process_ticket(ticket_id: str) -> None:
    """Guard, classify and draft one ticket, save what each part produced, then gate it."""
    try:
        row = await ticket_service.start_processing(ticket_id)
    except ticket_service.IllegalTransition as exc:
        # Escalated or resolved by a person: nothing left to draft for.
        logger.info("Ticket %s not processed: %s", ticket_id, exc)
        return
    except Exception as exc:
        logger.exception("Ticket %s: could not start processing", ticket_id)
        await _fail(ticket_id, "fetch", {"error": _error_text(exc)})
        return

    # The root run's id in LangSmith, stored on the draft so feedback can find the trace.
    run_id = uuid4()
    try:
        state = await get_ticket_graph().ainvoke(
            {
                "ticket_id": ticket_id,
                "ticket_no": row.get("ticket_no"),
                "query": join_complaint(row["subject"], row.get("body")),
            },
            config={"run_id": run_id},
        )
    except Exception as exc:
        logger.exception("Ticket %s: the ticket graph failed", ticket_id)
        await _fail(ticket_id, "ticket_graph", {"error": _error_text(exc)})
        await _finish(ticket_id, "processing_failed", [])
        return

    if state.get("input_blocked"):
        reasons = state.get("guard_reasons", [])
        logger.warning("Ticket %s blocked by the input guard: %s", ticket_id, reasons)
        await _fail(ticket_id, "input_guard", {"reasons": reasons})
        await _finish(ticket_id, "needs_review", [f"Blocked by the input guard: {'; '.join(reasons)}"])
        return

    errors = state.get("errors", {})
    for failed_stage, error in errors.items():
        await _fail(ticket_id, failed_stage, {"error": error})

    classification = state.get("classification")
    if classification:
        await _save_classification(ticket_id, classification)

    # If drafting failed on a retry, `draft` holds the attempt that failed its checks; it is not saved.
    saved = False
    if state.get("draft") and DRAFT_REPLY not in errors:
        saved = await _save_draft(ticket_id, state, run_id)
    if not saved:
        await _finish(ticket_id, "processing_failed", [])
        return

    reasons = review_reasons(
        classification,
        row.get("severity", "normal"),
        bool(state.get("no_match")),
        state.get("grounded"),
        state.get("risk_flags", []),
    )
    await _finish(ticket_id, "needs_review" if reasons else "drafted", reasons)
