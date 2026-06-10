from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.rag.nodes import lookup_guard as lookup_guard_module
from cms.schemas.guardrails import GuardResult

CASE_HIT = (
    Document(
        page_content="COMPLAINT:\ncharged twice\n\nRESOLUTION:\nduplicate refunded",
        metadata={"doc_id": "case-1", "chunk_id": "c1", "title": "C-1001"},
    ),
    0.9,
)
STATE = {"query": "refund cases", "draft": "- Duplicate refunded [1].", "policy_hits": [], "case_hits": [CASE_HIT]}


def _install(monkeypatch, gai: GuardResult | Exception, nemo: GuardResult | None = None) -> list[tuple]:
    """Stub both checks and pin the kill switches; record what each check was given."""
    calls: list[tuple] = []

    async def fake_run_lookup_guard(draft, citations, context):
        calls.append(("gai", draft, [citation.marker for citation in citations], context))
        if isinstance(gai, Exception):
            raise gai
        return gai

    async def fake_check_output(query, draft, context):
        calls.append(("nemo", query, draft, context))
        return nemo or GuardResult(passed=True, text=draft)

    monkeypatch.setattr(lookup_guard_module, "run_lookup_guard", fake_run_lookup_guard)
    monkeypatch.setattr(lookup_guard_module, "check_output", fake_check_output)
    monkeypatch.setattr(get_settings(), "guardrails_enabled", True)
    monkeypatch.setattr(get_settings(), "nemo_rails_enabled", True)
    return calls


async def test_passing_answer_is_grounded(monkeypatch) -> None:
    calls = _install(monkeypatch, GuardResult(passed=True, text="x"))

    update = await lookup_guard_module.lookup_guard(STATE)

    assert update == {"grounded": True, "guard_reasons": []}
    # The cases-only context numbers from [1], and NeMo sees the same block.
    assert calls[0][2] == [1]
    assert "[1] C-1001" in calls[0][3]
    assert calls[1][0] == "nemo" and calls[1][3] == calls[0][3]


async def test_deterministic_failure_skips_nemo(monkeypatch) -> None:
    calls = _install(monkeypatch, GuardResult(passed=False, text="x", reasons=["uncited"]))

    update = await lookup_guard_module.lookup_guard(STATE)

    assert update == {"grounded": False, "guard_reasons": ["uncited"]}
    assert [call[0] for call in calls] == ["gai"]


async def test_a_guard_error_counts_as_ungrounded(monkeypatch) -> None:
    _install(monkeypatch, RuntimeError("presidio crashed"))

    update = await lookup_guard_module.lookup_guard(STATE)

    assert update == {"grounded": False, "guard_reasons": [get_settings().guard_error_reason]}


async def test_disabled_guardrails_leave_the_answer_unchecked(monkeypatch) -> None:
    calls = _install(monkeypatch, RuntimeError("must not run"))
    monkeypatch.setattr(get_settings(), "guardrails_enabled", False)

    update = await lookup_guard_module.lookup_guard(STATE)

    assert update == {"grounded": None}
    assert calls == []
