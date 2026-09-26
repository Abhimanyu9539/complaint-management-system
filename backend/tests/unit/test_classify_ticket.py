import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from cms.rag.nodes import classify_ticket as classify_module
from cms.schemas.ticket_classification import DepartmentCandidate, TicketClassification


class _FakeModel:
    """`with_structured_output` returns a canned runnable, so the real v1 template still renders."""

    def __init__(self, reply: TicketClassification) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        def run(prompt_value):
            self.prompts.append(prompt_value.to_string())
            return self.reply

        return RunnableLambda(run)


def _candidate(department: str, score: float) -> DepartmentCandidate:
    return DepartmentCandidate(department=department, score=score)


def _classification(candidates: list[DepartmentCandidate]) -> TicketClassification:
    return TicketClassification(
        candidates=candidates,
        category="faulty_product",
        suggested_severity="high",
        reason="A physical fault inside the warranty period.",
    )


def test_normalize_sums_to_one_and_sorts_best_first() -> None:
    ranked = classify_module.normalize_candidates(
        [_candidate("tech_support", 0.2), _candidate("warranty", 0.6)]
    )

    assert [c.department for c in ranked] == ["warranty", "tech_support"]
    assert [c.score for c in ranked] == pytest.approx([0.75, 0.25])


def test_normalize_merges_duplicate_departments() -> None:
    ranked = classify_module.normalize_candidates(
        [_candidate("billing", 0.3), _candidate("billing", 0.5), _candidate("sales", 0.5)]
    )

    assert [c.department for c in ranked] == ["billing", "sales"]
    assert sum(c.score for c in ranked) == pytest.approx(1.0)


def test_normalize_splits_evenly_when_every_score_is_zero() -> None:
    ranked = classify_module.normalize_candidates(
        [_candidate("returns", 0.0), _candidate("shipping", 0.0)]
    )

    assert [c.score for c in ranked] == pytest.approx([0.5, 0.5])


def test_format_departments_gives_one_line_per_row() -> None:
    text = classify_module.format_departments(
        [
            {"id": "warranty", "name": "Warranty", "description": "Warranty claims."},
            {"id": "billing", "name": "Billing", "description": "Charges and refunds."},
        ]
    )

    assert text.splitlines() == [
        "- warranty (Warranty): Warranty claims.",
        "- billing (Billing): Charges and refunds.",
    ]


async def test_core_returns_normalised_candidates_and_renders_the_prompt(monkeypatch) -> None:
    model = _FakeModel(_classification([_candidate("warranty", 0.8), _candidate("tech_support", 0.2)]))
    monkeypatch.setattr(classify_module, "get_chat_model", lambda name: model)

    async def fake_departments() -> str:
        return "- warranty (Warranty): Warranty claims."

    monkeypatch.setattr(classify_module, "_departments_text", fake_departments)

    complaint = classify_module.join_complaint(
        "X200 won't power on", "My X200 stopped turning on after two weeks."
    )
    result = await classify_module.classify_ticket_core(complaint)

    assert result.department == "warranty"
    assert result.confidence == pytest.approx(0.8)
    assert [c.department for c in result.candidates] == ["warranty", "tech_support"]
    assert "X200 won't power on\n\nMy X200 stopped turning on after two weeks." in model.prompts[0]
    assert "- warranty (Warranty): Warranty claims." in model.prompts[0]


def test_join_complaint_puts_the_subject_first() -> None:
    assert classify_module.join_complaint("Charged twice", "Order #6120") == "Charged twice\n\nOrder #6120"
    assert classify_module.join_complaint("Subject only", None) == "Subject only"


async def test_node_classifies_the_state_query(monkeypatch) -> None:
    seen: list[str] = []
    canned = _classification([_candidate("billing", 1.0)])

    async def fake_core(complaint: str) -> TicketClassification:
        seen.append(complaint)
        return canned

    monkeypatch.setattr(classify_module, "classify_ticket_core", fake_core)

    update = await classify_module.classify_ticket({"ticket_id": "t1", "query": "masked text"})

    assert seen == ["masked text"]
    assert update == {"classification": canned}


def test_schema_rejects_a_department_outside_the_twelve() -> None:
    with pytest.raises(ValidationError):
        DepartmentCandidate(department="account", score=0.9)
