from uuid import UUID

from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.rag.context import build_generation_context, guidance_hit
from cms.rag.nodes.find_precedents import precedent_hit
from cms.schemas.ticket_classification import (
    DepartmentCandidate,
    TicketClassification,
    TicketEntities,
)
from cms.services import ticket_pipeline
from cms.services.ticket_service import IllegalTransition

CLASSIFICATION = TicketClassification(
    candidates=[
        DepartmentCandidate(department="warranty", score=0.75),
        DepartmentCandidate(department="tech_support", score=0.25),
    ],
    category="faulty_product",
    suggested_severity="high",
    entities=TicketEntities(order_no="#4521", product="X200"),
    reason="A physical fault inside the warranty period.",
)

POLICY_HIT = (
    Document(
        page_content="Warranty > 2.3 Charging\nHardware faults within 24 months are repaired free.",
        metadata={"doc_id": "p1", "chunk_id": "pc1", "title": "Warranty"},
    ),
    0.71,
)
CASE_HIT = (
    Document(
        page_content="COMPLAINT:\nX100 dead after a month.\n\nRESOLUTION:\nReplaced under warranty.",
        metadata={"doc_id": "c1", "chunk_id": "cc1", "title": "X100 dead"},
    ),
    0.5,
)
# The drafter cited the policy ([1]) and not the case ([2]).
CITED = build_generation_context([POLICY_HIT], [CASE_HIT])[2][:1]

DRAFTED = {
    "classification": CLASSIFICATION,
    "policy_hits": [POLICY_HIT],
    "case_hits": [CASE_HIT],
    "no_match": False,
    "draft": "Dear customer,\n\nYour X200 is covered for a free repair [1].",
    "citations": CITED,
    "grounded": True,
    "guard_reasons": [],
    "risk_flags": ["safety"],
}

DEPT_RESPONSE = {
    "id": "r1",
    "ticket_id": "t1",
    "department_id": "warranty",
    "answer_text": "Approve a replacement unit; no proof of purchase needed.",
    "created_at": "2026-10-02T10:00:00Z",
}
GUIDANCE_HIT = guidance_hit(DEPT_RESPONSE, "Warranty")


class _FakeGraph:
    def __init__(self, result: dict | Exception) -> None:
        self.result = result
        self.inputs: list[dict] = []
        self.configs: list[dict] = []

    async def ainvoke(self, state: dict, config: dict | None = None) -> dict:
        self.inputs.append(state)
        self.configs.append(config or {})
        if isinstance(self.result, Exception):
            raise self.result
        # Like LangGraph, the final state still holds the input.
        return {**state, **self.result}


def _install(
    monkeypatch,
    graph_result: dict | Exception,
    latest_draft: dict | None = None,
    insert_error=None,
    severity: str = "normal",
    start_error: Exception | None = None,
    responses: list[dict] | None = None,
    responses_error: Exception | None = None,
):
    """Stub the status changes, the graph and every write. Returns (graph, updates, events, inserted).

    `responses` are the department answers on the ticket; none by default.

    `finishes` (the gate's outcomes) is attached to the graph as `graph.finishes`.
    """
    graph = _FakeGraph(graph_result)
    graph.finishes = []
    updates: list[tuple[str, dict]] = []
    events: list[tuple[str, str, dict]] = []
    inserted: list[dict] = []

    async def start_processing(ticket_id):
        if start_error:
            raise start_error
        return {
            "id": ticket_id,
            "ticket_no": 1042,
            "severity": severity,
            "subject": "X200 won't charge",
            "body": "Order #4521, dead after 3 months.",
        }

    async def finish_processing(ticket_id, status, reasons):
        graph.finishes.append((status, reasons))

    async def update_ticket(ticket_id, patch):
        updates.append((ticket_id, patch))
        return {"id": ticket_id, **patch}

    async def append_event(ticket_id, event, payload=None, actor_id=None):
        events.append((ticket_id, event, payload))

    async def fetch_latest_draft(ticket_id, kind="customer_reply"):
        return latest_draft

    async def insert_draft(row):
        if insert_error:
            raise insert_error
        inserted.append(row)
        return {"id": "d1", **row}

    async def list_responses(ticket_id):
        if responses_error:
            raise responses_error
        return responses or []

    async def list_departments():
        return [{"id": "warranty", "name": "Warranty"}]

    monkeypatch.setattr(ticket_pipeline.dept_responses, "list_responses", list_responses)
    monkeypatch.setattr(ticket_pipeline.departments, "list_departments", list_departments)
    monkeypatch.setattr(ticket_pipeline.ticket_service, "start_processing", start_processing)
    monkeypatch.setattr(ticket_pipeline.ticket_service, "finish_processing", finish_processing)
    monkeypatch.setattr(ticket_pipeline.tickets, "update_ticket", update_ticket)
    monkeypatch.setattr(ticket_pipeline.ticket_events, "append_event", append_event)
    monkeypatch.setattr(ticket_pipeline.drafts, "fetch_latest_draft", fetch_latest_draft)
    monkeypatch.setattr(ticket_pipeline.drafts, "insert_draft", insert_draft)
    monkeypatch.setattr(ticket_pipeline, "get_ticket_graph", lambda: graph)
    return graph, updates, events, inserted


def _event_names(events) -> list[str]:
    return [event for _, event, _ in events]


async def test_classified_and_drafted_ticket_is_saved(monkeypatch) -> None:
    graph, updates, events, inserted = _install(monkeypatch, DRAFTED)

    await ticket_pipeline.process_ticket("t1")

    assert graph.inputs == [
        {
            "ticket_id": "t1",
            "ticket_no": 1042,
            "query": "X200 won't charge\n\nOrder #4521, dead after 3 months.",
            "guidance_hits": [],
        }
    ]
    run_id = graph.configs[0]["run_id"]
    assert isinstance(run_id, UUID)

    assert updates == [
        (
            "t1",
            {
                "predicted_dept": "warranty",
                "dept_confidence": 0.75,
                "category": "faulty_product",
                "entities": {"order_no": "#4521", "product": "X200"},
                "suggested_severity": "high",
                "dept_candidates": [
                    {"department": "warranty", "score": 0.75},
                    {"department": "tech_support", "score": 0.25},
                ],
            },
        )
    ]

    [row] = inserted
    assert row["version"] == 1
    assert row["kind"] == "customer_reply"
    assert row["draft_text"] == DRAFTED["draft"]
    assert row["no_match"] is False and row["grounded"] is True and row["guard_reasons"] == []
    assert row["model"] == get_settings().openrouter_model_main
    assert row["prompt_version"] == get_settings().customer_reply_prompt_version
    assert row["langsmith_run_id"] == str(run_id)
    assert row["policy_refs"][0]["policy_id"] == "p1"
    assert row["policy_refs"][0]["cited"] is True
    assert row["retrieved_cases"][0]["case_id"] == "c1"
    assert row["retrieved_cases"][0]["cited"] is False
    assert row["guidance_refs"] == []

    assert _event_names(events) == ["classified", "drafted"]
    assert events[1][2]["draft_id"] == "d1"
    assert events[1][2]["risk_flags"] == ["safety"]
    # Confidence 0.75 clears the floor, but the safety flag sends it to review.
    assert graph.finishes == [("needs_review", ["Risk flagged: safety."])]


async def test_clean_draft_is_gated_to_drafted(monkeypatch) -> None:
    graph, _, _, _ = _install(monkeypatch, {**DRAFTED, "risk_flags": []})

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("drafted", [])]


async def test_ticket_that_cannot_be_processed_is_left_alone(monkeypatch) -> None:
    graph, updates, events, _ = _install(
        monkeypatch, DRAFTED, start_error=IllegalTransition("resolved", "processing")
    )

    await ticket_pipeline.process_ticket("t1")

    assert graph.inputs == [] and updates == [] and events == [] and graph.finishes == []


async def test_a_rerun_saves_the_next_version(monkeypatch) -> None:
    _, _, _, inserted = _install(monkeypatch, DRAFTED, latest_draft={"version": 2})

    await ticket_pipeline.process_ticket("t1")

    assert inserted[0]["version"] == 3


async def test_holding_reply_is_saved_as_no_match(monkeypatch) -> None:
    holding = {
        "classification": CLASSIFICATION,
        "policy_hits": [],
        "case_hits": [CASE_HIT],
        "no_match": True,
        "draft": "Dear customer, ... T-1042 ...",
        "citations": [],
    }
    _, _, events, inserted = _install(monkeypatch, holding)

    await ticket_pipeline.process_ticket("t1")

    [row] = inserted
    assert row["no_match"] is True
    assert row["grounded"] is None
    assert row["model"] == get_settings().holding_reply_model
    assert row["prompt_version"] == get_settings().holding_reply_prompt_version
    assert _event_names(events) == ["classified", "drafted"]


async def test_ungrounded_draft_is_saved_with_its_reasons(monkeypatch) -> None:
    ungrounded = {**DRAFTED, "grounded": False, "regenerated": True, "guard_reasons": ["bad figure"]}
    _, _, _, inserted = _install(monkeypatch, ungrounded)

    await ticket_pipeline.process_ticket("t1")

    assert inserted[0]["grounded"] is False
    assert inserted[0]["guard_reasons"] == ["bad figure"]


async def test_drafting_failure_keeps_the_classification(monkeypatch) -> None:
    failed = {**DRAFTED, "grounded": False, "errors": {"draft_reply": "TimeoutError: slow"}}
    _, updates, events, inserted = _install(monkeypatch, failed)

    await ticket_pipeline.process_ticket("t1")

    assert len(updates) == 1
    # The draft in state is the attempt that failed its checks; it is not saved.
    assert inserted == []
    assert events[0] == ("t1", "failed", {"stage": "draft_reply", "error": "TimeoutError: slow"})
    assert _event_names(events) == ["failed", "classified"]


async def test_drafting_failure_ends_at_processing_failed(monkeypatch) -> None:
    failed = {**DRAFTED, "errors": {"draft_reply": "TimeoutError: slow"}}
    graph, _, _, _ = _install(monkeypatch, failed)

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("processing_failed", [])]


async def test_classification_failure_still_saves_the_draft(monkeypatch) -> None:
    result = {**DRAFTED, "errors": {"classify_ticket": "ValueError: bad json"}}
    del result["classification"]
    _, updates, events, inserted = _install(monkeypatch, result)

    await ticket_pipeline.process_ticket("t1")

    assert updates == []
    assert len(inserted) == 1
    assert _event_names(events) == ["failed", "drafted"]


async def test_draft_save_failure_is_recorded(monkeypatch) -> None:
    _, updates, events, _ = _install(monkeypatch, DRAFTED, insert_error=ConnectionError("down"))

    await ticket_pipeline.process_ticket("t1")

    assert len(updates) == 1
    assert _event_names(events) == ["classified", "failed"]
    assert events[1][2] == {"stage": "save_draft", "error": "ConnectionError: down"}


async def test_blocked_ticket_is_left_alone_with_a_failed_event(monkeypatch) -> None:
    _, updates, events, inserted = _install(
        monkeypatch, {"input_blocked": True, "guard_reasons": ["injection"]}
    )

    await ticket_pipeline.process_ticket("t1")

    assert updates == [] and inserted == []
    assert events == [("t1", "failed", {"stage": "input_guard", "reasons": ["injection"]})]


async def test_blocked_ticket_goes_to_review(monkeypatch) -> None:
    graph, _, _, _ = _install(monkeypatch, {"input_blocked": True, "guard_reasons": ["injection"]})

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("needs_review", ["Blocked by the input guard: injection"])]


async def test_graph_failure_is_recorded_and_not_raised(monkeypatch) -> None:
    _, updates, events, _ = _install(monkeypatch, ConnectionError("getaddrinfo failed"))

    await ticket_pipeline.process_ticket("t1")

    assert updates == []
    assert events == [
        ("t1", "failed", {"stage": "ticket_graph", "error": "ConnectionError: getaddrinfo failed"})
    ]


async def test_graph_failure_ends_at_processing_failed(monkeypatch) -> None:
    graph, _, _, _ = _install(monkeypatch, ConnectionError("getaddrinfo failed"))

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("processing_failed", [])]


async def test_draft_save_failure_ends_at_processing_failed(monkeypatch) -> None:
    graph, _, _, _ = _install(monkeypatch, DRAFTED, insert_error=ConnectionError("down"))

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("processing_failed", [])]


def test_case_resolution_reads_the_resolution_section() -> None:
    assert ticket_pipeline.case_resolution(CASE_HIT[0].page_content) == "Replaced under warranty."
    assert ticket_pipeline.case_resolution("COMPLAINT:\nno resolution here") is None


def test_evidence_rows_pair_each_offered_chunk_with_its_score() -> None:
    retrieved_cases, policy_refs, guidance_refs = ticket_pipeline.evidence_rows(
        [POLICY_HIT], [CASE_HIT], CITED
    )

    assert guidance_refs == []

    assert policy_refs == [
        {
            "marker": 1,
            "chunk_id": "pc1",
            "policy_id": "p1",
            "title": "Warranty",
            "snippet": "Hardware faults within 24 months are repaired free.",
            "score": 0.71,
            "cited": True,
            "section": "Warranty > 2.3 Charging",
        }
    ]
    assert retrieved_cases[0]["marker"] == 2
    assert retrieved_cases[0]["score"] == 0.5
    assert retrieved_cases[0]["resolution"] == "Replaced under warranty."


# --- after an escalation: the department's answer is a source ---

# The drafter cited the department's answer ([1]) and the policy ([2]).
GUIDED_CITED = build_generation_context([GUIDANCE_HIT, POLICY_HIT], [CASE_HIT])[2][:2]
GUIDED = {
    **DRAFTED,
    "draft": "Dear customer,\n\nWe will send a replacement [1][2].",
    "citations": GUIDED_CITED,
    "risk_flags": [],
}


async def test_department_answer_reaches_the_graph(monkeypatch) -> None:
    graph, _, _, _ = _install(monkeypatch, GUIDED, responses=[DEPT_RESPONSE])

    await ticket_pipeline.process_ticket("t1")

    [hit] = graph.inputs[0]["guidance_hits"]
    assert hit[0].metadata["title"] == "Department guidance — Warranty"
    assert "Approve a replacement unit" in hit[0].page_content


async def test_guided_run_ends_at_dept_responded_and_saves_the_guidance(monkeypatch) -> None:
    graph, _, _, inserted = _install(monkeypatch, GUIDED, responses=[DEPT_RESPONSE])

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("dept_responded", [])]
    [row] = inserted
    assert row["guidance_refs"] == [
        {
            "marker": 1,
            "dept_response_id": "r1",
            "department_id": "warranty",
            "title": "Department guidance — Warranty",
            "snippet": "Approve a replacement unit; no proof of purchase needed.",
            "cited": True,
        }
    ]
    # The policy moves to [2] behind the answer.
    assert row["policy_refs"][0]["marker"] == 2 and row["policy_refs"][0]["cited"] is True


async def test_guided_run_keeps_its_review_reasons(monkeypatch) -> None:
    graph, _, _, _ = _install(
        monkeypatch, {**GUIDED, "risk_flags": ["safety"]}, responses=[DEPT_RESPONSE]
    )

    await ticket_pipeline.process_ticket("t1")

    assert graph.finishes == [("dept_responded", ["Risk flagged: safety."])]


async def test_no_policy_match_with_an_answer_is_not_a_holding_reply(monkeypatch) -> None:
    result = {**GUIDED, "policy_hits": [], "no_match": True}
    _, _, _, inserted = _install(monkeypatch, result, responses=[DEPT_RESPONSE])

    await ticket_pipeline.process_ticket("t1")

    assert inserted[0]["no_match"] is False
    assert inserted[0]["model"] == get_settings().openrouter_model_main


async def test_failed_answer_read_ends_at_processing_failed(monkeypatch) -> None:
    graph, _, events, _ = _install(monkeypatch, GUIDED, responses_error=ConnectionError("down"))

    await ticket_pipeline.process_ticket("t1")

    assert graph.inputs == []
    assert events == [("t1", "failed", {"stage": "fetch_guidance", "error": "ConnectionError: down"})]
    assert graph.finishes == [("processing_failed", [])]


# --- an earlier department answer from a similar past case ---

PRECEDENT_CASE = Document(
    page_content=(
        "COMPLAINT:\nX200 battery smoked on the dock.\n\n"
        "DEPARTMENT GUIDANCE:\nBatch under internal review; refund it.\n\n"
        "RESOLUTION:\nRefunded."
    ),
    metadata={
        "doc_id": "c9",
        "chunk_id": "cc9",
        "title": "C-1009 — product_safety / safety_hazard",
        "department": "product_safety",
    },
)
PRECEDENT_TITLE = "Earlier department guidance (C-1009 — product_safety / safety_hazard)"
# Offered as [1] the earlier answer, [2] the policy, [3] the same case as a past case.
PRECEDENT_OFFERED = build_generation_context(
    [precedent_hit(PRECEDENT_CASE, 0.82), POLICY_HIT], [(PRECEDENT_CASE, 0.5)]
)[2]
PRECEDED = {
    **DRAFTED,
    "case_hits": [(PRECEDENT_CASE, 0.5)],
    "precedent_hits": [precedent_hit(PRECEDENT_CASE, 0.82)],
    "draft": "Dear customer,\n\nWe will refund you [1][2].",
    "citations": PRECEDENT_OFFERED[:2],
    "risk_flags": [],
}


async def test_cited_precedent_is_saved_and_sent_to_review(monkeypatch) -> None:
    graph, _, _, inserted = _install(monkeypatch, PRECEDED)

    await ticket_pipeline.process_ticket("t1")

    [row] = inserted
    assert row["guidance_refs"] == [
        {
            "marker": 1,
            "dept_response_id": "c9",
            "department_id": "product_safety",
            "title": PRECEDENT_TITLE,
            "snippet": "Batch under internal review; refund it.",
            "cited": True,
        }
    ]
    assert row["policy_refs"][0]["marker"] == 2
    assert graph.finishes == [
        ("needs_review", [f"Relies on {PRECEDENT_TITLE}. Check it applies to this complaint."])
    ]


async def test_uncited_precedent_adds_no_reason(monkeypatch) -> None:
    # Citing the same case as a past case ([3]) is not relying on its department answer.
    uncited = {**PRECEDED, "draft": "Dear customer [2][3].", "citations": PRECEDENT_OFFERED[1:]}
    graph, _, _, inserted = _install(monkeypatch, uncited)

    await ticket_pipeline.process_ticket("t1")

    assert inserted[0]["guidance_refs"][0]["cited"] is False
    assert graph.finishes == [("drafted", [])]
