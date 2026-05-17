"""Custom Guardrails AI validators: credential masking and the draft's grounding checks.

Failure messages are written as instructions, because the output guard feeds them
back to the model when it regenerates a draft.
"""

import re
from typing import Any

from guardrails.validator_base import (
    FailResult,
    PassResult,
    ValidationResult,
    Validator,
    register_validator,
)

from cms.rag.context import MARKER_PATTERN

CREDENTIAL_MASK = "<CREDENTIAL>"

# An amount, a percentage or a duration: "₹8,000", "Rs. 500", "15%", "30 days", "12-month".
NUMERIC_CLAIM = re.compile(
    r"(?:₹|\brs\.?|\binr)\s*(\d[\d,]*(?:\.\d+)?)"
    r"|(\d[\d,]*(?:\.\d+)?)\s*-?\s*"
    r"(?:%|per\s?cent\b|(?:business |working )?(?:days?|weeks?|months?|years?|hours?)\b)",
    re.IGNORECASE,
)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalise(number: str) -> str:
    return number.replace(",", "")


@register_validator(name="cms/mask_credentials", data_type="string")
class MaskCredentials(Validator):
    """Masks an OTP, UPI PIN or CVV and its digits — Presidio has no recognizer for these."""

    def __init__(self, pattern: str, on_fail: Any = None, **kwargs):
        super().__init__(on_fail=on_fail, pattern=pattern, **kwargs)
        self._pattern = re.compile(pattern)

    def _validate(self, value: str, metadata: dict[str, Any]) -> ValidationResult:
        masked = self._pattern.sub(CREDENTIAL_MASK, value)
        if masked == value:
            return PassResult()
        return FailResult(error_message="The text contains a credential.", fix_value=masked)


@register_validator(name="cms/citations_valid", data_type="string")
class CitationsValid(Validator):
    """The draft cites at least one source, and every `[n]` is a source it was given.

    Expects `metadata["citations"]`: the `Citation`s offered to the model.
    """

    def _validate(self, value: str, metadata: dict[str, Any]) -> ValidationResult:
        offered = {citation.marker for citation in metadata.get("citations", [])}
        markers = {int(marker) for marker in MARKER_PATTERN.findall(value)}
        if not markers:
            return FailResult(
                error_message="The draft cites no source. End every claim with the [n] of its source."
            )
        unknown = sorted(markers - offered)
        if unknown:
            return FailResult(
                error_message=(
                    f"The draft cites {unknown}, which are not among the numbered sources. "
                    "Cite only the numbers you were given."
                )
            )
        return PassResult()


@register_validator(name="cms/numbers_in_sources", data_type="string")
class NumbersInSources(Validator):
    """Every amount, percentage and duration in the draft appears in the sources (ai §2).

    Expects `metadata["context"]`: the policy and case text offered to the model.
    Checks against everything offered, not only what was cited — simpler, and it
    still catches the invented "60-day window" the policy warns about.
    """

    def _validate(self, value: str, metadata: dict[str, Any]) -> ValidationResult:
        sources = {_normalise(number) for number in NUMBER.findall(metadata.get("context", ""))}
        prose = MARKER_PATTERN.sub(" ", value)
        claimed = {
            _normalise(amount or duration) for amount, duration in NUMERIC_CLAIM.findall(prose)
        }
        missing = sorted(claimed - sources)
        if missing:
            return FailResult(
                error_message=(
                    f"The draft states the figures {missing}, which appear in no source. "
                    "Remove every amount, period or percentage the sources do not give."
                )
            )
        return PassResult()


@register_validator(name="cms/policy_cited", data_type="string")
class PolicyCited(Validator):
    """A draft that cites past cases also cites policy: precedent alone authorises nothing.

    Expects `metadata["citations"]`. A draft citing nothing is `CitationsValid`'s failure.
    """

    def _validate(self, value: str, metadata: dict[str, Any]) -> ValidationResult:
        markers = {int(marker) for marker in MARKER_PATTERN.findall(value)}
        cited_types = {
            citation.doc_type
            for citation in metadata.get("citations", [])
            if citation.marker in markers
        }
        if "case" in cited_types and "policy" not in cited_types:
            return FailResult(
                error_message=(
                    "The draft rests only on past cases. Cite the policy extract that "
                    "authorises the remedy, or say that policy does not cover it."
                )
            )
        return PassResult()
