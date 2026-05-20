from guardrails.validator_base import FailResult, PassResult

from cms.guardrails.validators import (
    CREDENTIAL_MASK,
    CitationsValid,
    MaskCredentials,
    NumbersInSources,
    PolicyCited,
)
from cms.schemas.generation import Citation

POLICY = Citation(marker=1, doc_id="p", chunk_id="p1", title="Warranty", section="2.3")
CASE = Citation(marker=2, doc_id="k", chunk_id="k1", title="C-1001", section="c", doc_type="case")
CONTEXT = "[1] Warranty\nDefects within 12 months are replaced. Refunds up to ₹8,000.\n\n[2] C-1001"


def test_credentials_are_masked() -> None:
    from cms.config.settings import get_settings

    validator = MaskCredentials(pattern=get_settings().credential_pattern)

    result = validator.validate("I shared my OTP is 482913 and CVV 123 with them.", {})

    assert isinstance(result, FailResult)
    assert "482913" not in result.fix_value and "123" not in result.fix_value
    assert result.fix_value.count(CREDENTIAL_MASK) == 2


def test_postal_pin_code_is_not_a_credential() -> None:
    from cms.config.settings import get_settings

    validator = MaskCredentials(pattern=get_settings().credential_pattern)

    assert isinstance(validator.validate("Deliver to pin code 560001.", {}), PassResult)


def test_uncited_draft_fails() -> None:
    result = CitationsValid().validate("It is covered.", {"citations": [POLICY]})

    assert isinstance(result, FailResult)


def test_unknown_marker_fails() -> None:
    result = CitationsValid().validate("Covered [1], refunded [7].", {"citations": [POLICY]})

    assert isinstance(result, FailResult)
    assert "[7]" in result.error_message


def test_valid_citations_pass() -> None:
    assert isinstance(CitationsValid().validate("Covered [1].", {"citations": [POLICY]}), PassResult)


def test_invented_figures_fail() -> None:
    draft = "Replaced within 60 days [1], with ₹5,000 compensation [1]."

    result = NumbersInSources().validate(draft, {"context": CONTEXT})

    assert isinstance(result, FailResult)
    assert "'5000'" in result.error_message and "'60'" in result.error_message


def test_figures_from_the_sources_pass_in_any_format() -> None:
    draft = "A 12-month warranty [1] covers it; refunds up to Rs. 8000 [1]."

    assert isinstance(NumbersInSources().validate(draft, {"context": CONTEXT}), PassResult)


def test_citation_markers_are_not_figures() -> None:
    assert isinstance(NumbersInSources().validate("Covered [12].", {"context": ""}), PassResult)


def test_draft_citing_only_cases_fails() -> None:
    result = PolicyCited().validate("A similar case was refunded [2].", {"citations": [POLICY, CASE]})

    assert isinstance(result, FailResult)


def test_draft_citing_policy_and_case_passes() -> None:
    draft = "Covered [1]; a similar case was replaced [2]."

    assert isinstance(PolicyCited().validate(draft, {"citations": [POLICY, CASE]}), PassResult)
