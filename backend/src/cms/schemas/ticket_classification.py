"""The structured output of the `classify_ticket` step: who owns a ticket, and how urgent it looks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cms.schemas.tickets import TicketSeverity

# The closed set seeded by migration 0003. A new department means a migration and an edit here.
DepartmentId = Literal[
    "warranty",
    "billing",
    "shipping",
    "product_safety",
    "returns",
    "tech_support",
    "qa",
    "legal",
    "sales",
    "manufacturing",
    "retention",
    "spare_parts",
]

# The seed cases' categories, plus `other`. Closed so per-category metrics aggregate.
TicketCategory = Literal[
    "faulty_product",
    "safety_concern",
    "duplicate_charge",
    "subscription_billing",
    "pricing_error",
    "lost_package",
    "damaged_in_transit",
    "safety_hazard",
    "late_return_request",
    "change_of_mind",
    "connectivity_issue",
    "hardware_malfunction",
    "app_pairing",
    "quality_defect",
    "injury_claim",
    "promo_not_applied",
    "batch_defect",
    "cancellation_request",
    "part_request",
    "other",
]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class DepartmentCandidate(_Base):
    department: DepartmentId
    score: float = Field(ge=0, le=1, description="How likely this department owns the ticket.")


class TicketEntities(_Base):
    """Identifiers copied verbatim from the complaint; null when not stated."""

    order_no: str | None = None
    invoice_no: str | None = None
    product: str | None = None
    amount: str | None = None
    error_code: str | None = None


class TicketClassification(_Base):
    """One `classify_ticket` call. Scores are self-reported, so treat confidence as uncalibrated."""

    candidates: list[DepartmentCandidate] = Field(
        min_length=1,
        max_length=3,
        description="Departments that could own the ticket, most likely first.",
    )
    category: TicketCategory
    suggested_severity: TicketSeverity = Field(
        description="A suggestion only: a human confirms severity (severity §5)."
    )
    entities: TicketEntities = Field(default_factory=TicketEntities)
    reason: str = Field(description="One sentence on why the top department owns it.")

    @property
    def department(self) -> DepartmentId:
        return self.candidates[0].department

    @property
    def confidence(self) -> float:
        return self.candidates[0].score
