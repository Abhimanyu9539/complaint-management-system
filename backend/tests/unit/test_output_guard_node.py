from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.rag.nodes import output_guard as output_guard_module
from cms.schemas.guardrails import GuardResult

HIT = (
    Document(
        page_content="Warranty > 2.3 Defects\n\ncovered for replacement",
        metadata={"doc_id": "doc-1", "chunk_id": "c1", "title": "Warranty Policy"},
    ),
    0.9,
)
STATE = {"query": "unit stopped charging", "draft": "Covered [1].", "policy_hits": [HIT], "case_hits": []}


def _install(monkeypatch, gai: GuardResult | Exception, nemo: GuardResult | None = None) -> list[tuple]:
    """Stub both checks; record what each was given."""
    calls: list[tuple] = []

    async def fake_run_output_guard(draft, citations, context):
        calls.append(("gai", draft, [citation.marker for citation in citations], context))
        if isinstance(gai, Exception):
            raise gai
        return gai

    async def fake_check_output(query, draft, context):
        calls.append(("nemo", query, draft, context))
        return nemo or GuardResult(passed=True, text=draft)

    monkeypatch.setattr(output_guard_module, "run_output_guard", fake_run_output_guard)
    monkeypatch.setattr(output_guard_module, "check_output", fake_check_output)
    return calls


async def test_passing_draft_is_grounded(monkeypatch) -> None:
    calls = _install(monkeypatch, GuardResult(passed=True, text="Covered [1]."))

    update = await output_guard_module.output_guard(STATE)

    assert update == {"grounded": True, "guard_reasons": []}
    # Both checks see the same numbered context generate was shown.
    assert calls[0][2] == [1]
    assert "[1] Warranty Policy" in calls[0][3]
    assert calls[1][0] == "nemo" and calls[1][3] == calls[0][3]


async def test_deterministic_failure_skips_nemo(monkeypatch) -> None:
    calls = _install(monkeypatch, GuardResult(passed=False, text="x", reasons=["uncited"]))

    update = await output_guard_module.output_guard(STATE)

    assert update == {"grounded": False, "guard_reasons": ["uncited"]}
    assert [call[0] for call in calls] == ["gai"]


async def test_nemo_block_is_ungrounded(monkeypatch) -> None:
    _install(
        monkeypatch,
        GuardResult(passed=True, text="x"),
        nemo=GuardResult(passed=False, text="x", reasons=["unsupported claim"]),
    )

    update = await output_guard_module.output_guard(STATE)

    assert update == {"grounded": False, "guard_reasons": ["unsupported claim"]}


async def test_a_guard_error_counts_as_ungrounded(monkeypatch) -> None:
    _install(monkeypatch, RuntimeError("nemo timed out"))

    update = await output_guard_module.output_guard(STATE)

    assert update == {"grounded": False, "guard_reasons": [get_settings().guard_error_reason]}


async def test_disabled_guardrails_leave_the_draft_unchecked(monkeypatch) -> None:
    calls = _install(monkeypatch, RuntimeError("must not run"))
    monkeypatch.setattr(get_settings(), "guardrails_enabled", False)

    update = await output_guard_module.output_guard(STATE)

    assert update == {"grounded": None}
    assert calls == []
