from nemoguardrails.rails.llm.options import RailsResult, RailStatus

from cms.config.settings import get_settings
from cms.guardrails import nemo_rails as nemo_module
from cms.schemas.guardrails import UnsupportedClaim

DRAFT = "Covered within a 60-day window [1]."
CONTEXT = "[1] Warranty\nCovered for 12 months."


class _FakeRails:
    """Stands in for `LLMRails`: `check_async` returns a canned verdict."""

    def __init__(self, result: RailsResult) -> None:
        self.result = result

    async def check_async(self, messages, rail_types=None) -> RailsResult:
        return self.result


def _install(
    monkeypatch, status: RailStatus, rail: str | None, finder: list | Exception | None = None
) -> list[tuple]:
    """Stub NeMo and the claim finder; record what the finder was given."""
    result = RailsResult(status=status, content="I'm sorry, I can't respond to that.", rail=rail)
    monkeypatch.setattr(nemo_module, "get_output_rails", lambda: _FakeRails(result))
    calls: list[tuple] = []

    async def fake_find_unsupported_claims(draft: str, context: str):
        calls.append((draft, context))
        if isinstance(finder, Exception):
            raise finder
        return finder or []

    monkeypatch.setattr(nemo_module, "find_unsupported_claims", fake_find_unsupported_claims)
    return calls


async def test_fact_check_block_names_the_unsupported_claims(monkeypatch) -> None:
    claims = [UnsupportedClaim(claim="a 60-day window", reason="[1] says 12 months, not 60 days.")]
    calls = _install(monkeypatch, RailStatus.BLOCKED, "self check facts", claims)

    result = await nemo_module.check_output("q", DRAFT, CONTEXT)

    assert not result.passed
    assert result.reasons == ['"a 60-day window": [1] says 12 months, not 60 days.']
    assert calls == [(DRAFT, CONTEXT)]


async def test_fact_check_block_with_no_claims_stays_blocked(monkeypatch) -> None:
    _install(monkeypatch, RailStatus.BLOCKED, "self check facts", [])

    result = await nemo_module.check_output("q", DRAFT, CONTEXT)

    # A disagreement never lets a draft through.
    assert not result.passed
    assert result.reasons == [get_settings().rail_feedback["self check facts"]]


async def test_claim_finder_error_keeps_the_generic_reason(monkeypatch) -> None:
    _install(monkeypatch, RailStatus.BLOCKED, "self check facts", RuntimeError("model down"))

    result = await nemo_module.check_output("q", DRAFT, CONTEXT)

    assert not result.passed
    assert result.reasons == [get_settings().rail_feedback["self check facts"]]


async def test_output_rail_block_does_not_run_the_claim_finder(monkeypatch) -> None:
    calls = _install(monkeypatch, RailStatus.BLOCKED, "self check output")

    result = await nemo_module.check_output("q", DRAFT, CONTEXT)

    assert not result.passed
    assert result.reasons == [get_settings().rail_feedback["self check output"]]
    assert calls == []


async def test_passing_draft_does_not_run_the_claim_finder(monkeypatch) -> None:
    calls = _install(monkeypatch, RailStatus.PASSED, None)

    result = await nemo_module.check_output("q", DRAFT, CONTEXT)

    assert result.passed
    assert result.reasons == []
    assert calls == []


def test_input_and_output_rails_use_their_own_models(monkeypatch) -> None:
    built: list[tuple[str, dict]] = []
    monkeypatch.setattr(nemo_module, "_build_rails", lambda model, rails: built.append((model, rails)))
    nemo_module.get_input_rails.cache_clear()
    nemo_module.get_output_rails.cache_clear()

    try:
        nemo_module.get_input_rails()
        nemo_module.get_output_rails()
    finally:
        # Never leave a stubbed build in the process-wide cache.
        nemo_module.get_input_rails.cache_clear()
        nemo_module.get_output_rails.cache_clear()

    settings = get_settings()
    assert built == [
        (settings.openrouter_model_cheap, {"input": {"flows": ["self check input"]}}),
        (settings.guard_judge_model, {"output": {"flows": ["self check facts", "self check output"]}}),
    ]
