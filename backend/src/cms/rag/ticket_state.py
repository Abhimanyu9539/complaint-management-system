"""`TicketState`: what the ticket graph carries for one ticket run.

Key names match `GraphState` where the meaning is the same, so shared nodes
such as `input_guard` run on either graph unchanged.
"""

from typing import TypedDict

from cms.schemas.ticket_classification import TicketClassification


class _RequiredState(TypedDict):
    ticket_id: str
    # Subject and body as one text; `input_guard` replaces it with the masked version.
    query: str


class TicketState(_RequiredState, total=False):
    # --- guardrails (input_guard) ---
    input_blocked: bool
    guard_reasons: list[str]

    # --- triage (classify_ticket) ---
    classification: TicketClassification
