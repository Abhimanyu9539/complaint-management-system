"""The real guards, end to end. Presidio runs locally, so no network — but it loads spaCy."""

from cms.guardrails.guards import run_input_guard, run_output_guard
from cms.schemas.generation import Citation

CITATIONS = [Citation(marker=1, doc_id="p", chunk_id="p1", title="Warranty", section="2.3")]
CONTEXT = "[1] Warranty\nCharging failures within 12 months get a free replacement."


async def test_input_guard_masks_every_sensitive_value_together() -> None:
    result = await run_input_guard(
        "Card 4111 1111 1111 1111 charged twice. Aadhaar 2345 6789 0124, PAN ABCDE1234F, "
        "OTP is 482913, email a.b@example.com."
    )

    assert result.passed
    for raw in ("4111", "2345 6789 0124", "ABCDE1234F", "482913", "a.b@example.com"):
        assert raw not in result.text
    for mask in ("<CREDIT_CARD>", "<IN_AADHAAR>", "<IN_PAN>", "<CREDENTIAL>", "<EMAIL_ADDRESS>"):
        assert mask in result.text


async def test_input_guard_rejects_text_that_is_too_short() -> None:
    result = await run_input_guard("hi")

    assert not result.passed
    assert result.reasons


async def test_output_guard_passes_a_grounded_draft() -> None:
    result = await run_output_guard(
        "Covered: failures within 12 months get a free replacement [1].", CITATIONS, CONTEXT
    )

    assert result.passed
    assert result.reasons == []


async def test_output_guard_reports_every_failed_check() -> None:
    result = await run_output_guard(
        "Covered for 60 days [3]. Email a.b@example.com.", CITATIONS, CONTEXT
    )

    assert not result.passed
    # Unknown marker, invented figure, and personal data — one reason each.
    assert len(result.reasons) == 3
