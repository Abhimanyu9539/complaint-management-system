"""Guardrails AI guards: deterministic checks on the complaint going in and the draft coming out."""

import logging
from functools import lru_cache

from guardrails import AsyncGuard, OnFailAction
from guardrails.errors import ValidationError
from guardrails.validator_base import Validator
from guardrails_ai.detect_pii import DetectPII
from guardrails_ai.valid_length import ValidLength
from presidio_analyzer.predefined_recognizers import (
    InAadhaarRecognizer,
    InPanRecognizer,
)

from cms.config.settings import get_settings
from cms.guardrails.validators import (
    CitationsValid,
    MaskCredentials,
    NumbersInSources,
    PolicyCited,
)
from cms.schemas.generation import Citation
from cms.schemas.guardrails import GuardResult

logger = logging.getLogger(__name__)

# Presidio warns once per non-English recognizer it skips, every time an engine is built.
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)


def _pii_validator(on_fail: OnFailAction) -> DetectPII:
    """DetectPII with Presidio's Aadhaar and PAN recognizers, which ship disabled."""
    validator = DetectPII(
        pii_entities=get_settings().pii_entities, on_fail=on_fail, use_local=True
    )
    validator.pii_analyzer.registry.add_recognizer(InAadhaarRecognizer())
    validator.pii_analyzer.registry.add_recognizer(InPanRecognizer())
    return validator


def _build_guard(*validators: Validator) -> AsyncGuard:
    # One `use` call on purpose: a second `use` replaces the first one's validators.
    guard = AsyncGuard().use(*validators)
    # Hub telemetry is on by default and would ship spans off the machine.
    guard.configure(allow_metrics_collection=False)
    return guard


@lru_cache
def get_input_guard() -> AsyncGuard:
    """Length bounds, then Presidio and credential masking. Built once: Presidio loads spaCy."""
    settings = get_settings()
    try:
        return _build_guard(
            ValidLength(
                min=settings.query_min_chars,
                max=settings.query_max_chars,
                on_fail=OnFailAction.EXCEPTION,
            ),
            _pii_validator(OnFailAction.FIX),
            MaskCredentials(pattern=settings.credential_pattern, on_fail=OnFailAction.FIX),
        )
    except Exception:
        logger.exception("Failed to build the input guard")
        raise


@lru_cache
def get_output_guard() -> AsyncGuard:
    """The draft's grounding checks plus Presidio. Every failure is reported, none fixed."""
    try:
        return _build_guard(
            CitationsValid(on_fail=OnFailAction.NOOP),
            NumbersInSources(on_fail=OnFailAction.NOOP),
            PolicyCited(on_fail=OnFailAction.NOOP),
            _pii_validator(OnFailAction.NOOP),
        )
    except Exception:
        logger.exception("Failed to build the output guard")
        raise


async def run_input_guard(query: str) -> GuardResult:
    """The complaint with sensitive data masked, or a failure if its length is out of bounds."""
    try:
        outcome = await get_input_guard().validate(query)
    except ValidationError as exc:
        logger.warning("input guard: rejected: %s", exc)
        return GuardResult(passed=False, text="", reasons=[str(exc)])
    except Exception:
        logger.exception("input guard: validation crashed")
        raise

    if not outcome.validation_passed or outcome.validated_output is None:
        logger.warning("input guard: no validated output")
        return GuardResult(passed=False, text="", reasons=[get_settings().guard_error_reason])

    masked_by = [summary.validator_name for summary in outcome.validation_summaries or []]
    logger.info("input guard: passed, masked by %s", masked_by or "nothing")
    return GuardResult(passed=True, text=outcome.validated_output)


async def run_output_guard(draft: str, citations: list[Citation], context: str) -> GuardResult:
    """Grounding and PII checks on `draft`, given the citations and context it was written from."""
    try:
        outcome = await get_output_guard().validate(
            draft, metadata={"citations": citations, "context": context}
        )
    except Exception:
        logger.exception("output guard: validation crashed")
        raise

    reasons = [
        # DetectPII's own message repeats the whole draft; give the model a short instruction.
        get_settings().draft_pii_reason
        if summary.validator_name == DetectPII.__name__
        else summary.failure_reason
        for summary in outcome.validation_summaries or []
        if summary.validator_status == "fail"
    ]
    logger.info("output guard: %d failed check(s) %s", len(reasons), reasons)
    return GuardResult(passed=not reasons, text=draft, reasons=reasons)
