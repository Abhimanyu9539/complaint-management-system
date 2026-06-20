"""The gate: decide whether a drafted ticket needs a closer look before its reply goes out."""

import logging

from cms.config.settings import get_settings
from cms.schemas.ticket_classification import TicketClassification

logger = logging.getLogger(__name__)


def review_reasons(
    classification: TicketClassification | None,
    severity: str,
    no_match: bool,
    grounded: bool | None,
    risk_flags: list[str],
) -> list[str]:
    """Every reason this ticket needs review, in words the workbench shows as-is.

    Empty means the ticket is `drafted`; anything else means `needs_review`.
    """
    floor = get_settings().routing_confidence_floor
    reasons: list[str] = []

    if classification is None:
        reasons.append("No department prediction.")
    elif classification.confidence < floor:
        reasons.append(
            f"Department confidence {classification.confidence:.0%} is below {floor:.0%}."
        )
    if no_match:
        reasons.append("No policy matched; the draft is only a holding reply.")
    if grounded is False:
        reasons.append("The draft failed the automated checks twice.")
    if risk_flags:
        reasons.append(f"Risk flagged: {', '.join(risk_flags)}.")
    suggested = classification.suggested_severity if classification else None
    if "critical" in (severity, suggested):
        reasons.append("Critical severity.")

    logger.info("gate: %d review reason(s) %s", len(reasons), reasons)
    return reasons
