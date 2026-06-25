"""`TicketState`: what the ticket graph carries for one ticket run.

Key names match `GraphState` where the meaning is the same, so shared nodes
such as `input_guard` and the retrieval nodes run on either graph unchanged.
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.documents import Document

from cms.schemas.generation import Citation
from cms.schemas.query_analysis import RiskFlag
from cms.schemas.ticket_classification import TicketClassification


class _RequiredState(TypedDict):
    ticket_id: str
    # Subject and body as one text; `input_guard` replaces it with the masked version.
    query: str


class TicketState(_RequiredState, total=False):
    # The customer's reference number, for the holding reply.
    ticket_no: int

    # --- guardrails (input_guard, ticket_output_guard) ---
    input_blocked: bool
    guard_reasons: list[str]

    # --- triage (classify_ticket) ---
    classification: TicketClassification

    # --- query analysis (analyze_ticket) ---
    policy_queries: list[str]
    risk_flags: list[RiskFlag]

    # --- department answers (set by the pipeline after an escalation) ---
    guidance_hits: list[tuple[Document, float]]  # newest first, offered before the policies

    # --- retrieval ---
    policy_hits: list[tuple[Document, float]]  # (chunk, score), best first
    case_hits: list[tuple[Document, float]]  # (chunk, score), best first
    no_match: bool

    # --- drafting (draft_reply or ticket_no_match) ---
    draft: str
    citations: list[Citation]
    grounded: bool | None
    regenerated: bool

    # Stage -> error, for nodes that failed without ending the run. Parallel
    # branches can both write it, so updates are merged.
    errors: Annotated[dict[str, str], operator.or_]


def drafting_sources(state: TicketState) -> list[tuple[Document, float]]:
    """What the drafter cites before the cases: department answers first, then policies."""
    return state.get("guidance_hits", []) + state.get("policy_hits", [])


def needs_holding_reply(state: TicketState) -> bool:
    """No policy matched and no department has answered, so there is nothing to draft from."""
    return bool(state.get("no_match")) and not state.get("guidance_hits")
