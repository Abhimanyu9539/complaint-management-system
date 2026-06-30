from cms.schemas.ticket_classification import DepartmentCandidate, TicketClassification
from cms.services.ticket_gate import review_reasons


def _classification(confidence: float, suggested_severity: str = "normal") -> TicketClassification:
    candidates = [DepartmentCandidate(department="warranty", score=confidence)]
    if confidence < 1:
        candidates.append(DepartmentCandidate(department="billing", score=1 - confidence))
    return TicketClassification(
        candidates=candidates,
        category="faulty_product",
        suggested_severity=suggested_severity,
        reason="r",
    )


def _reasons(**overrides) -> list[str]:
    args = {
        "classification": _classification(0.9),
        "severity": "normal",
        "no_match": False,
        "grounded": True,
        "risk_flags": [],
        "precedents": [],
    }
    return review_reasons(**{**args, **overrides})


def test_clean_ticket_has_no_reasons() -> None:
    assert _reasons() == []


def test_unchecked_draft_is_not_a_reason() -> None:
    # grounded=None means the guardrails were off, not that the draft failed.
    assert _reasons(grounded=None) == []


def test_missing_classification() -> None:
    assert _reasons(classification=None) == ["No department prediction."]


def test_low_confidence() -> None:
    assert _reasons(classification=_classification(0.42)) == [
        "Department confidence 42% is below 60%."
    ]


def test_no_match() -> None:
    assert _reasons(no_match=True) == ["No policy matched; the draft is only a holding reply."]


def test_ungrounded_draft() -> None:
    assert _reasons(grounded=False) == ["The draft failed the automated checks twice."]


def test_risk_flags() -> None:
    assert _reasons(risk_flags=["legal", "safety"]) == ["Risk flagged: legal, safety."]


def test_critical_severity_from_the_ticket_or_the_classifier() -> None:
    assert _reasons(severity="critical") == ["Critical severity."]
    assert _reasons(classification=_classification(0.9, "critical")) == ["Critical severity."]


def test_precedent() -> None:
    title = "Earlier department guidance (T-14 — product_safety / safety)"
    assert _reasons(precedents=[title]) == [f"Relies on {title}. Check it applies to this complaint."]


def test_reasons_accumulate() -> None:
    assert len(_reasons(classification=None, no_match=True, grounded=False)) == 3
