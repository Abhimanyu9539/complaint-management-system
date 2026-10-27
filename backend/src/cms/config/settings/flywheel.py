"""Flywheel: the daily job that turns resolved tickets into past cases."""

from pydantic import BaseModel


class FlywheelSettings(BaseModel):
    # --- Flywheel (a resolved ticket becomes a past case) ---
    # Kill switch: off, the daily job mints no case.
    flywheel_enabled: bool = True
    # Mirrors the seed `case_title`, with the ticket in place of the case id.
    flywheel_case_title_template: str = "T-{ticket_no} — {department} / {category}"
    # The ticket's own identifiers, replaced before Presidio runs (privacy §6).
    case_entity_masks: dict[str, str] = {"order_no": "<ORDER_NO>", "invoice_no": "<INVOICE_NO>"}

    # --- Flywheel daily job (Airflow calls /api/v1/flywheel/*) ---
    # The shared secret Airflow sends as `X-Job-Secret`. Unset turns the job endpoints off (503).
    flywheel_job_secret: str | None = None
    # A "day" runs midnight to midnight IST. IST has no daylight saving, so a fixed offset is exact.
    flywheel_day_utc_offset_minutes: int = 330
    # Cap on the tickets one day's run lists.
    flywheel_batch_max_tickets: int = 500
    # A past case at or above this rerank score is compared with the new one. Same scale and
    # reasoning as `precedent_relevance_threshold`; the judge, not this score, decides.
    flywheel_similar_case_threshold: float = 0.70
    # Past cases the judge compares at most.
    flywheel_dedupe_top_n: int = 3
