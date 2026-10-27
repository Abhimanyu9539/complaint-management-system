"""Drafting: context size, citations, ticket routing, department guidance and the holding reply."""

from pydantic import BaseModel


class GenerationSettings(BaseModel):
    # --- Generation ---
    # A guard, not a shaper: 12 reranked chunks measure at ~2,400 tokens, so this
    # only trips if policy_rerank_top_n is raised or a chunk arrives oversized.
    generation_context_tokens: int = 4000
    # How much of a chunk a citation carries for the UI's sources panel. Long
    # enough to judge the match, short enough not to resend the context block.
    citation_snippet_chars: int = 300

    # --- Ticket routing ---
    # Intake §7: a top department at or above this routes directly; below goes to human review.
    routing_confidence_floor: float = 0.60

    # --- Department guidance and precedents ---
    # Title of a department's answer when it is offered to the drafter as a source.
    guidance_title_template: str = "Department guidance — {department}"
    # Kill switch: off, a past case's department answer is only precedent, never a source.
    precedents_enabled: bool = True
    # Reranker score a past case needs before its department answer is offered as a source.
    # Stricter than `policy_relevance_threshold`; tune it from the `ticket-precedents` eval's logged scores.
    precedent_relevance_threshold: float = 0.70
    # `{case}` is the case title, e.g. "T-14 — product_safety / safety".
    precedent_title_template: str = "Earlier department guidance ({case})"

    # --- Holding reply (its text is `holding_reply_message`) ---
    # Stored as `drafts.model` / `drafts.prompt_version` for a holding reply; both columns are NOT NULL.
    holding_reply_model: str = "template"
    holding_reply_prompt_version: str = "holding_reply"
