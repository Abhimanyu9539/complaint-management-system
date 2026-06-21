"""Request and response contracts for the ticket surface.

`schemas/admin.py` set the pattern for this package and stated one rule it could
not yet test: "Response models only. Request bodies arrive as query parameters
today, and there is nothing to model until there is a POST." This module is that
POST, so the rule extends rather than breaks:

- Request models are named `*Request` and live beside the responses they cause.
- Everything else from `admin.py` still holds: snake_case matching the wire,
  `frozen=True`, `Literal[...]` rather than `Enum`, timestamps as raw ISO `str`.

One addition the response-only modules never needed: **every string field on a
request model is bounded.** `POST /api/v1/tickets` is reachable without
authentication (see the route module and `backend/docs/admin-api.md` §9), so an
unbounded TEXT column is an unbounded write. These limits are the only thing
standing between the form and a multi-megabyte insert, which makes them part of
the contract rather than defensive decoration.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketStatus = Literal[
    "new",
    "processing",
    "drafted",
    "needs_review",
    "escalated",
    "dept_responded",
    "resolved",
    "processing_failed",
]

TicketSeverity = Literal["low", "normal", "high", "critical"]

# What a customer may choose. `critical` is deliberately absent: a public
# urgency picker offering the top of the scale is a picker where everything is
# critical. Triage raises it, which keeps the label meaningful.
CustomerSeverity = Literal["low", "normal", "high"]

TicketSource = Literal["email", "web", "agent"]

ResolutionPath = Literal["direct", "escalated"]

# Deliberately permissive. This rejects the obvious non-addresses without
# pretending to validate deliverability, which no regex can do — a customer
# whose valid address this refused would simply lose their complaint.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateTicketRequest(_Base):
    """What the customer-facing form submits.

    Note what is *not* here: `predicted_dept`, `category` and `entities` are the
    classifier's outputs, not the customer's inputs. Asking a customer to route
    their own complaint is how misrouting happens, and a department field would
    additionally become an unauthenticated write into a FK-constrained column.
    """

    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(
        min_length=10,
        max_length=8000,
        description="The complaint itself. Stored in `tickets.body` (migration 0017).",
    )
    customer_email: str = Field(
        max_length=254,
        pattern=EMAIL_PATTERN,
        description="Required for web intake — a complaint with no reply address cannot be answered.",
    )
    severity: CustomerSeverity = Field(
        default="normal",
        description="A hint from the customer, not a commitment. Triage may change it.",
    )


class EscalateTicketRequest(_Base):
    """Hand a ticket to a specialist department.

    `department_id` is checked against the closed set of twelve before it is
    written, so a bad value is a 422 rather than a foreign-key error surfacing
    as a 500.
    """

    department_id: str = Field(min_length=1, max_length=64)
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional context for the department. Stored on the ticket_events row.",
    )


class ResolveTicketRequest(_Base):
    """Close a ticket.

    Carries no `resolution_path`: the path is *derived* from whether the ticket
    was ever escalated, not chosen at resolution time. Letting a client assert
    it would let the north-star metric be set by hand.
    """

    note: str | None = Field(default=None, max_length=2000)


class SendReplyRequest(_Base):
    """Send the (possibly edited) draft to the customer by email.

    `final_text` may still carry the draft's [n] markers; they are removed before sending.
    """

    draft_id: str = Field(min_length=1, max_length=64)
    final_text: str = Field(min_length=1, max_length=8000)


DiscardReason = Literal["wrong_case", "wrong_tone", "wrong_policy", "other"]


class DiscardDraftRequest(_Base):
    """Reject a draft. The reason is the training label (`draft_feedback.edit_reason`)."""

    draft_id: str = Field(min_length=1, max_length=64)
    reason: DiscardReason
    note: str | None = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class TicketCreated(_Base):
    """The 201 body. Deliberately minimal — the customer needs a reference."""

    id: str
    ticket_no: int = Field(description="Human reference, rendered as T-1042.")
    status: TicketStatus
    created_at: str


class Ticket(_Base):
    id: str
    ticket_no: int
    status: TicketStatus
    severity: TicketSeverity
    subject: str
    body: str | None = Field(
        default=None,
        description="Null for tickets created before migration 0017, or ingested subject-only.",
    )
    source: TicketSource
    customer_email: str | None = None
    predicted_dept: str | None = Field(
        default=None, description="The classifier's top department. Null until the ticket graph has run."
    )
    dept_confidence: float | None = None
    escalated_dept: str | None = Field(
        default=None,
        description="The department actually escalated to. Non-null implies the ticket took Path B.",
    )
    category: str | None = None
    entities: dict = Field(
        default_factory=dict,
        description="Identifiers the classifier copied from the complaint: order_no, product, ...",
    )
    suggested_severity: TicketSeverity | None = Field(
        default=None,
        description="The classifier's suggestion. `severity` changes only when a person confirms it.",
    )
    dept_candidates: list[dict] = Field(
        default_factory=list,
        description="[{department, score}], best first, scores summing to 1. Empty until classified.",
    )
    review_reasons: list[str] = Field(
        default_factory=list,
        description="Why the gate sent this ticket to `needs_review`, in plain words. Empty otherwise.",
    )
    resolution_path: ResolutionPath | None = Field(
        default=None,
        description=(
            "Null until resolved, and that null is meaningful: it means 'not yet "
            "decided', not 'direct'. This is the column the escalation-rate "
            "metric reads (lld.md:257)."
        ),
    )
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class TicketEvent(_Base):
    """One row of the append-only audit log."""

    id: int
    event: str = Field(
        description="Free text by design — migration 0016 puts no CHECK on it. See `ticket_events.EVENTS`."
    )
    payload: dict
    actor_id: str | None = Field(default=None, description="Null means the system acted.")
    created_at: str


class CaseEvidence(_Base):
    """A past case the drafter was offered. `marker` is its `[n]` in the draft."""

    marker: int
    case_id: str
    chunk_id: str
    title: str
    snippet: str = ""
    resolution: str | None = None
    score: float = Field(description="Hybrid (RRF) score: ranks cases within one ticket, not a similarity.")
    cited: bool


class PolicyEvidence(_Base):
    """A policy chunk the drafter was offered. `marker` is its `[n]` in the draft."""

    marker: int
    policy_id: str
    chunk_id: str
    title: str
    section: str = ""
    snippet: str = ""
    score: float = Field(description="Reranker score, 0-1.")
    cited: bool


class DraftFeedback(_Base):
    """What an agent did with a draft: sent it as-is, sent it edited, or rejected it."""

    action: Literal["accepted", "edited", "rejected"]
    final_text: str | None = Field(default=None, description="Exactly what was emailed. Null when rejected.")
    edit_reason: DiscardReason | None = None
    created_at: str


class TicketDraft(_Base):
    """The latest reply drafted for the customer, with the evidence it was written from."""

    id: str
    version: int
    draft_text: str = Field(description="Keeps its [n] markers; they are removed when the reply is sent.")
    no_match: bool = Field(description="No policy matched, so this is the holding reply.")
    grounded: bool | None = Field(
        default=None,
        description="False: still failed the output guard after one retry. Null: not checked.",
    )
    guard_reasons: list[str] = Field(default_factory=list)
    retrieved_cases: list[CaseEvidence] = Field(default_factory=list)
    policy_refs: list[PolicyEvidence] = Field(default_factory=list)
    model: str
    prompt_version: str
    created_at: str
    feedback: DraftFeedback | None = Field(
        default=None, description="Null until the draft is sent or discarded."
    )


class TicketDetail(_Base):
    """A ticket plus its history and latest draft — one request backs the whole drawer."""

    ticket: Ticket
    events: list[TicketEvent]
    draft: TicketDraft | None = Field(default=None, description="Null until the ticket graph has drafted.")


class TicketPage(_Base):
    items: list[Ticket]
    total: int
    limit: int
    offset: int
