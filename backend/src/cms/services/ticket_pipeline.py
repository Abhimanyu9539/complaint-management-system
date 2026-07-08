"""Run the ticket graph for one ticket and save what it produced.

Runs as a background task after a ticket is created, so it never raises: a
failure is logged and written as a `failed` event, and the ticket stays visible
for a person to handle. The classification and the draft are saved separately,
so one failing never loses the other.

The ticket moves `processing` → `drafted` | `needs_review` | `processing_failed`;
`ticket_gate.review_reasons` decides between the first two. A ticket a department
has answered is drafted from that answer too, and goes back to `dept_responded`.
A draft citing a similar past case's department answer gets a review reason.
Every graph run is recorded in `agent_runs` for the admin's activity page.
"""

import logging
import time
from uuid import UUID, uuid4

from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.db.repositories import (
    agent_runs,
    departments,
    dept_responses,
    drafts,
    ticket_events,
    tickets,
    utc_now_iso,
)
from cms.rag.context import build_generation_context, guidance_hit
from cms.rag.nodes.classify_ticket import join_complaint
from cms.rag.ticket_graph import DRAFT_REPLY, get_ticket_graph
from cms.rag.ticket_state import TicketState, needs_holding_reply
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
    guidance_hits: list[tuple[Document, float]] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """`(retrieved_cases, policy_refs, guidance_refs)`: every source the drafter was offered.

    `guidance_hits` holds this ticket's department answers, then the past cases'.
    The offered citations are rebuilt the way the drafter built them, department
    answers first. They keep the hits' order and stop at the context budget, so
    zipping pairs each with its hit.
    """
    guidance_hits = guidance_hits or []
    _, _, offered = build_generation_context(guidance_hits + policy_hits, case_hits)
    cited_markers = {citation.marker for citation in cited}
    offered_guidance = [c for c in offered if c.doc_type == "guidance"]
    offered_policies = [c for c in offered if c.doc_type == "policy"]
    offered_cases = [c for c in offered if c.doc_type == "case"]

    guidance_refs = [
        {
            "marker": citation.marker,
            "dept_response_id": citation.doc_id,
            "department_id": document.metadata.get("department_id", ""),
            "title": citation.title,
            "snippet": citation.snippet,
            "cited": citation.marker in cited_markers,
        }
        for citation, (document, _score) in zip(offered_guidance, guidance_hits)
    ]

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
    return retrieved_cases, policy_refs, guidance_refs


def cited_precedents(state: TicketState) -> list[str]:
    """Titles of the past cases' department answers the draft cites.

    Matched on guidance citations only: the same case may also be offered, and cited, as a past case.
    """
    cited = {c.doc_id for c in state.get("citations", []) if c.doc_type == "guidance"}
    return [
        document.metadata["title"]
        for document, _score in state.get("precedent_hits", [])
        if document.metadata.get("doc_id") in cited
    ]


async def _guidance_hits(ticket_id: str) -> list[tuple[Document, float]]:
    """Every department answer on the ticket, newest first, as hits the drafter can cite."""
    responses = await dept_responses.list_responses(ticket_id)
    if not responses:
        return []
    names = {row["id"]: row["name"] for row in await departments.list_departments()}
    return [
        guidance_hit(response, names.get(response["department_id"], response["department_id"]))
        for response in responses
    ]


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
    no_match = needs_holding_reply(state)
    model = settings.holding_reply_model if no_match else settings.openrouter_model_main
    prompt_version = (
        settings.holding_reply_prompt_version if no_match else settings.customer_reply_prompt_version
    )
    grounded = state.get("grounded")

    try:
        latest = await drafts.fetch_latest_draft(ticket_id)
        version = latest["version"] + 1 if latest else 1
        retrieved_cases, policy_refs, guidance_refs = evidence_rows(
            state.get("policy_hits", []),
            state.get("case_hits", []),
            state.get("citations", []),
            state.get("guidance_hits", []) + state.get("precedent_hits", []),
        )
        saved = await drafts.insert_draft(
            {
                "ticket_id": ticket_id,
                "version": version,
                "kind": drafts.CUSTOMER_REPLY,
                "draft_text": state["draft"],
                "retrieved_cases": retrieved_cases,
                "policy_refs": policy_refs,
                "guidance_refs": guidance_refs,
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


def run_status(state: TicketState, outcome: str) -> str:
    """How a graph run ended, for the activity log: `failed`, `blocked`, `no_match` or `succeeded`."""
    if outcome == "processing_failed":
        return "failed"
    if state.get("input_blocked"):
        return "blocked"
    if needs_holding_reply(state):
        return "no_match"
    return "succeeded"


async def _record_run(
    run: dict, state: TicketState, outcome: str, reasons: list[str], latency_ms: int
) -> None:
    """Write the run's row in `agent_runs`. `insert_run` swallows its own failures."""
    classification = state.get("classification")
    status = run_status(state, outcome)
    await agent_runs.insert_run(
        {
            **run,
            "status": status,
            "outcome": outcome,
            "review_reasons": reasons,
            "predicted_dept": classification.department if classification else None,
            "dept_confidence": classification.confidence if classification else None,
            "category": classification.category if classification else None,
            "grounded": state.get("grounded"),
            "regenerated": bool(state.get("regenerated")),
            "precedents_offered": len(state.get("precedent_hits", [])),
            "steps": state.get("steps", []),
            "errors": state.get("errors", {}),
            "latency_ms": latency_ms,
            "finished_at": utc_now_iso(),
        }
    )
    logger.info(
        "Ticket %s run %s: %s, gated to %s in %d ms", run["ticket_id"], run["id"], status, outcome, latency_ms
    )


async def _save_and_gate(
    ticket_id: str,
    row: dict,
    state: TicketState,
    run_id: UUID,
    guidance_hits: list[tuple[Document, float]],
) -> tuple[str, list[str]]:
    """Save what the run produced, then pick the ticket's next status. Returns `(status, reasons)`."""
    if state.get("input_blocked"):
        reasons = state.get("guard_reasons", [])
        logger.warning("Ticket %s blocked by the input guard: %s", ticket_id, reasons)
        await _fail(ticket_id, "input_guard", {"reasons": reasons})
        return "needs_review", [f"Blocked by the input guard: {'; '.join(reasons)}"]

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
        return "processing_failed", []

    reasons = review_reasons(
        classification,
        row.get("severity", "normal"),
        needs_holding_reply(state),
        state.get("grounded"),
        state.get("risk_flags", []),
        cited_precedents(state),
    )
    # Redrafted from a department's answer: back to the top of the queue, reasons still shown.
    if guidance_hits:
        return "dept_responded", reasons
    return ("needs_review" if reasons else "drafted"), reasons


async def process_ticket(ticket_id: str, trigger: str = "created") -> None:
    """Guard, classify and draft one ticket, save what each part produced, then gate it.

    `trigger` says why it ran (`agent_runs.TRIGGERS`), for the activity log.
    """
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

    # Drafting without a department's answer would undo the escalation, so a failed read stops here.
    try:
        guidance_hits = await _guidance_hits(ticket_id)
    except Exception as exc:
        logger.exception("Ticket %s: reading the department answers failed", ticket_id)
        await _fail(ticket_id, "fetch_guidance", {"error": _error_text(exc)})
        await _finish(ticket_id, "processing_failed", [])
        return

    # The root run's id in LangSmith, stored on the draft so feedback can find the trace.
    run_id = uuid4()
    run = {
        "id": str(run_id),
        "ticket_id": ticket_id,
        "ticket_no": row.get("ticket_no"),
        "subject": row.get("subject"),
        "trigger": trigger,
        "started_at": utc_now_iso(),
    }
    start = time.perf_counter()
    try:
        state = await get_ticket_graph().ainvoke(
            {
                "ticket_id": ticket_id,
                "ticket_no": row.get("ticket_no"),
                "query": join_complaint(row["subject"], row.get("body")),
                "guidance_hits": guidance_hits,
            },
            config={"run_id": run_id},
        )
    except Exception as exc:
        logger.exception("Ticket %s: the ticket graph failed", ticket_id)
        error = _error_text(exc)
        latency_ms = round((time.perf_counter() - start) * 1000)
        await _fail(ticket_id, "ticket_graph", {"error": error})
        await _finish(ticket_id, "processing_failed", [])
        await _record_run(run, {"errors": {"ticket_graph": error}}, "processing_failed", [], latency_ms)
        return
    latency_ms = round((time.perf_counter() - start) * 1000)

    status, reasons = await _save_and_gate(ticket_id, row, state, run_id, guidance_hits)
    await _finish(ticket_id, status, reasons)
    await _record_run(run, state, status, reasons, latency_ms)
