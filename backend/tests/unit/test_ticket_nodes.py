from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.llm.prompts.registry import load_prompt
from cms.rag.nodes import analyze_ticket as analyze_ticket_module
from cms.rag.nodes import draft_reply as draft_reply_module
from cms.rag.nodes import ticket_output_guard as guard_module
from cms.rag.nodes.ticket_no_match import ticket_no_match
from cms.schemas.guardrails import GuardResult
from cms.schemas.query_analysis import QueryAnalysis

HIT = (
    Document(
        page_content="Warranty > 2.3 Defects\n\nFaults within 24 months are repaired free.",
        metadata={"doc_id": "doc-1", "chunk_id": "c1", "title": "Warranty Policy"},
    ),
    0.9,
)
STATE = {
    "ticket_id": "t1",
    "query": "X200 dead after 3 months",
    "draft": "Dear customer, it is covered [1].",
    "policy_hits": [HIT],
    "case_hits": [],
}


# --- customer_reply prompt ---


def test_customer_reply_prompt_takes_the_generate_variables() -> None:
    prompt = load_prompt("customer_reply", get_settings().customer_reply_prompt_version)

    assert set(prompt.input_variables) == {"context", "cases", "query", "feedback"}


# --- draft_reply ---


def _stub_generate_core(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    async def fake_core(query, policy_hits, case_hits, **kwargs):
        calls.append({"query": query, **kwargs})
        return "Dear customer [1].", []

    monkeypatch.setattr(draft_reply_module, "generate_core", fake_core)
    return calls


async def test_draft_reply_uses_the_customer_prompt(monkeypatch) -> None:
    calls = _stub_generate_core(monkeypatch)

    update = await draft_reply_module.draft_reply(STATE)

    assert update == {"draft": "Dear customer [1].", "citations": []}
    assert calls[0]["prompt_name"] == "customer_reply"
    assert calls[0]["prompt_version"] == get_settings().customer_reply_prompt_version
    assert calls[0]["feedback"] is None and calls[0]["previous_draft"] is None


async def test_draft_reply_revises_the_failed_draft(monkeypatch) -> None:
    calls = _stub_generate_core(monkeypatch)
    state = {**STATE, "grounded": False, "guard_reasons": ["bad figure"]}

    update = await draft_reply_module.draft_reply(state)

    assert update["regenerated"] is True
    assert calls[0]["feedback"] == ["bad figure"]
    assert calls[0]["previous_draft"] == STATE["draft"]


# --- ticket_output_guard ---


def _install_guard(monkeypatch, gai: GuardResult | Exception, nemo_enabled: bool) -> list[tuple]:
    calls: list[tuple] = []

    async def fake_run_output_guard(draft, citations, context):
        calls.append(("gai", context))
        if isinstance(gai, Exception):
            raise gai
        return gai

    async def fake_check_customer_reply(query, draft, context):
        calls.append(("nemo", context))
        return GuardResult(passed=True, text=draft)

    monkeypatch.setattr(guard_module, "run_output_guard", fake_run_output_guard)
    monkeypatch.setattr(guard_module, "check_customer_reply", fake_check_customer_reply)
    monkeypatch.setattr(get_settings(), "nemo_rails_enabled", nemo_enabled)
    return calls


async def test_number_check_sees_the_complaint_but_the_fact_check_does_not(monkeypatch) -> None:
    calls = _install_guard(monkeypatch, GuardResult(passed=True, text="x"), nemo_enabled=True)

    update = await guard_module.ticket_output_guard(STATE)

    assert update == {"grounded": True, "guard_reasons": []}
    assert STATE["query"] in calls[0][1]
    assert calls[1][0] == "nemo" and STATE["query"] not in calls[1][1]
    assert "[1] Warranty Policy" in calls[1][1]


async def test_customer_check_is_skipped_when_nemo_is_off(monkeypatch) -> None:
    calls = _install_guard(monkeypatch, GuardResult(passed=True, text="x"), nemo_enabled=False)

    await guard_module.ticket_output_guard(STATE)

    assert [name for name, _ in calls] == ["gai"]


async def test_a_check_that_errors_counts_as_ungrounded(monkeypatch) -> None:
    _install_guard(monkeypatch, RuntimeError("presidio down"), nemo_enabled=False)

    update = await guard_module.ticket_output_guard(STATE)

    assert update == {"grounded": False, "guard_reasons": [get_settings().guard_error_reason]}


# --- ticket_no_match ---


async def test_holding_reply_carries_the_ticket_reference() -> None:
    update = await ticket_no_match({**STATE, "ticket_no": 1042})

    assert "T-1042" in update["draft"]
    assert update["citations"] == []


# --- analyze_ticket ---


async def test_analyze_ticket_keeps_the_original_text_first(monkeypatch) -> None:
    async def fake_core(query):
        return QueryAnalysis(
            intent="smalltalk_or_meta", policy_queries=["warranty repair"], risk_flags=["safety"]
        )

    monkeypatch.setattr(analyze_ticket_module, "analyze_query_core", fake_core)

    update = await analyze_ticket_module.analyze_ticket(STATE)

    # The intent is ignored: a ticket is always a complaint.
    assert update == {"policy_queries": [STATE["query"], "warranty repair"], "risk_flags": ["safety"]}


async def test_analyze_ticket_failure_falls_back_to_the_original_text(monkeypatch) -> None:
    async def fake_core(query):
        raise TimeoutError("slow")

    monkeypatch.setattr(analyze_ticket_module, "analyze_query_core", fake_core)

    update = await analyze_ticket_module.analyze_ticket(STATE)

    assert update == {"policy_queries": [STATE["query"]], "risk_flags": []}


# --- after an escalation ---

ANSWER = (
    Document(
        page_content="Department guidance\nReplace the unit.",
        metadata={"doc_id": "r1", "chunk_id": "r1", "title": "Department guidance — Warranty", "doc_type": "guidance"},
    ),
    1.0,
)


async def test_draft_reply_offers_the_department_answer_first(monkeypatch) -> None:
    offered: list = []

    async def fake_core(query, policy_hits, case_hits, **kwargs):
        offered.extend(policy_hits)
        return "Dear customer [1].", []

    monkeypatch.setattr(draft_reply_module, "generate_core", fake_core)

    await draft_reply_module.draft_reply({**STATE, "guidance_hits": [ANSWER]})

    assert offered == [ANSWER, HIT]


async def test_output_guard_checks_against_the_department_answer(monkeypatch) -> None:
    calls = _install_guard(monkeypatch, GuardResult(passed=True, text="x"), nemo_enabled=True)

    await guard_module.ticket_output_guard({**STATE, "guidance_hits": [ANSWER]})

    assert "[1] Department guidance — Warranty" in calls[1][1]
    assert "[2] Warranty Policy" in calls[1][1]
