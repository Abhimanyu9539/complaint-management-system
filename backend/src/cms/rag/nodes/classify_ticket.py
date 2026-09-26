"""Ticket-graph node: rank the departments that could own a complaint, suggest a severity,
and pull out its category and identifiers. One structured call per ticket.
"""

import logging
from typing import get_args

from langsmith import traceable

from cms.config.settings import get_settings
from cms.db.repositories.departments import list_department_descriptions
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.rag.ticket_state import TicketState
from cms.schemas.ticket_classification import (
    DepartmentCandidate,
    DepartmentId,
    TicketClassification,
)

logger = logging.getLogger(__name__)

# Rendered department list for the prompt. Descriptions change only by migration, so one read per process.
_departments_cache: str | None = None


def format_departments(rows: list[dict]) -> str:
    """One `- id (Name): description` line per department."""
    known = set(get_args(DepartmentId))
    found = {row["id"] for row in rows}
    if found != known:
        logger.warning(
            "departments table and DepartmentId differ: missing=%s, extra=%s",
            sorted(known - found),
            sorted(found - known),
        )
    return "\n".join(f"- {row['id']} ({row['name']}): {row['description']}" for row in rows)


async def _departments_text() -> str:
    """The department list for the prompt, read from the database once."""
    global _departments_cache
    if _departments_cache is None:
        _departments_cache = format_departments(await list_department_descriptions())
    return _departments_cache


def normalize_candidates(candidates: list[DepartmentCandidate]) -> list[DepartmentCandidate]:
    """Merge duplicate departments, sort best first, and rescale the scores to sum to 1."""
    best: dict[str, float] = {}
    for candidate in candidates:
        best[candidate.department] = max(best.get(candidate.department, 0.0), candidate.score)

    total = sum(best.values())
    ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
    if total == 0:
        # No signal at all: split evenly rather than divide by zero.
        return [DepartmentCandidate(department=dept, score=1 / len(ranked)) for dept, _ in ranked]
    return [DepartmentCandidate(department=dept, score=score / total) for dept, score in ranked]


def join_complaint(subject: str, body: str | None) -> str:
    """Subject and body as the one text the classifier and the ticket graph read."""
    return f"{subject}\n\n{body or ''}".strip()


@traceable(name="classify_ticket")
async def classify_ticket_core(complaint: str) -> TicketClassification:
    """Classify one ticket. Candidates come back normalised, so `confidence` is a share of 1."""
    settings = get_settings()
    prompt = load_prompt("classify_ticket", settings.classify_ticket_prompt_version)
    model = get_chat_model(settings.openrouter_model_cheap).with_structured_output(
        TicketClassification
    )
    chain = prompt | model
    subject = complaint.splitlines()[0] if complaint else ""

    try:
        departments = await _departments_text()
        raw = await chain.ainvoke({"departments": departments, "complaint": complaint})
    except Exception:
        logger.exception("classify_ticket failed for subject %r", subject)
        raise

    classification = raw.model_copy(update={"candidates": normalize_candidates(raw.candidates)})
    logger.info(
        "classify_ticket: %s (%.2f), runner-ups=%s, severity=%s, category=%s for %r",
        classification.department,
        classification.confidence,
        [(c.department, round(c.score, 2)) for c in classification.candidates[1:]],
        classification.suggested_severity,
        classification.category,
        subject,
    )
    return classification


async def classify_ticket(state: TicketState) -> dict:
    """The ticket-graph node: classify the (masked) ticket text."""
    return {"classification": await classify_ticket_core(state["query"])}
