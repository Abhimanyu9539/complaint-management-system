import pytest

from cms.config.settings import get_settings
from cms.schemas.guardrails import GuardResult
from cms.services import escalation_service
from cms.services.email_sender import EmailSendError
from cms.services.ticket_service import IllegalTransition, UnknownDepartment

TICKET = {
    "id": "t1",
    "ticket_no": 1042,
    "status": "needs_review",
    "subject": "Kettle stopped heating",
    "body": "Bought it in May, card 4111 1111 1111 1111.",
    "customer_email": "jo@example.com",
    "escalated_dept": None,
    "review_reasons": ["No policy matched; the draft is only a holding reply."],
}
DEPARTMENT = {
    "id": "warranty",
    "name": "Warranty",
    "mailbox": "warranty@example.com",
    "description": "Warranty claims.",
}
QUESTION_DRAFT = {"id": "q1", "ticket_id": "t1", "kind": "dept_question", "draft_text": "Is it covered?"}


def _install(
    monkeypatch, ticket=None, department=DEPARTMENT, email_error=None, question="Is it covered?"
) -> dict:
    """Stub every read, write, the model and the email. Returns a dict recording what happened."""
    calls = {
        "model": [],
        "drafts": [],
        "emails": [],
        "escalated": [],
        "responses": [],
        "responded": [],
        "actors": [],
    }
    ticket = ticket or TICKET

    async def fetch_ticket(ticket_id):
        return ticket

    async def fetch_department(department_id):
        if department is None:
            raise LookupError(department_id)
        return department

    async def fetch_latest_draft(ticket_id, kind="customer_reply"):
        if kind == "customer_reply":
            return {"version": 1, "draft_text": "Dear customer, we are looking into it [1]."}
        return None

    async def fetch_draft(draft_id):
        return QUESTION_DRAFT

    async def insert_draft(row):
        calls["drafts"].append(row)
        return {"id": "q2", **row}

    async def run_input_guard(text):
        return GuardResult(passed=True, text=text.replace("4111 1111 1111 1111", "<CREDIT_CARD>"))

    async def write_question(department, complaint, current_draft, review_reasons):
        calls["model"].append((department, complaint, current_draft, review_reasons))
        return question

    async def send_email(to, subject, body):
        calls["emails"].append((to, subject, body))
        if email_error:
            raise email_error
        return "<m1@example.com>"

    async def escalate_ticket(ticket_id, department_id, note=None, email=None, actor_id=None):
        calls["escalated"].append((department_id, note, email))
        calls["actors"].append(actor_id)
        return "escalated-ticket"

    async def insert_response(row):
        calls["responses"].append(row)
        return {"id": "r1", **row}

    async def mark_dept_responded(ticket_id, response, actor_id=None):
        calls["responded"].append(response)
        calls["actors"].append(actor_id)
        return "responded-ticket"

    monkeypatch.setattr(escalation_service.tickets, "fetch_ticket", fetch_ticket)
    monkeypatch.setattr(escalation_service.ticket_service.departments, "fetch_department", fetch_department)
    monkeypatch.setattr(escalation_service.drafts, "fetch_latest_draft", fetch_latest_draft)
    monkeypatch.setattr(escalation_service.drafts, "fetch_draft", fetch_draft)
    monkeypatch.setattr(escalation_service.drafts, "insert_draft", insert_draft)
    monkeypatch.setattr(escalation_service, "run_input_guard", run_input_guard)
    monkeypatch.setattr(escalation_service, "_write_question", write_question)
    monkeypatch.setattr(escalation_service, "send_email", send_email)
    monkeypatch.setattr(escalation_service.ticket_service, "escalate_ticket", escalate_ticket)
    monkeypatch.setattr(escalation_service.dept_responses, "insert_response", insert_response)
    monkeypatch.setattr(escalation_service.ticket_service, "mark_dept_responded", mark_dept_responded)
    monkeypatch.setattr(get_settings(), "guardrails_enabled", True)
    return calls


# --- draft_question ---


async def test_question_is_drafted_from_the_masked_complaint_and_saved(monkeypatch) -> None:
    calls = _install(monkeypatch)

    question = await escalation_service.draft_question("t1", "warranty")

    [(department, complaint, current_draft, reasons)] = calls["model"]
    assert department == DEPARTMENT
    assert "<CREDIT_CARD>" in complaint and "4111" not in complaint
    assert current_draft == "Dear customer, we are looking into it."
    assert reasons == TICKET["review_reasons"]

    [row] = calls["drafts"]
    assert row["kind"] == "dept_question" and row["version"] == 1
    assert row["draft_text"] == "Is it covered?"
    assert row["prompt_version"] == get_settings().dept_question_prompt_version
    assert question.draft_id == "q2" and question.text == "Is it covered?"


async def test_no_question_for_a_ticket_that_cannot_be_escalated(monkeypatch) -> None:
    calls = _install(monkeypatch, ticket={**TICKET, "status": "resolved"})

    with pytest.raises(IllegalTransition):
        await escalation_service.draft_question("t1", "warranty")
    assert calls["model"] == [] and calls["drafts"] == []


async def test_an_empty_question_is_not_saved(monkeypatch) -> None:
    calls = _install(monkeypatch, question="")

    with pytest.raises(RuntimeError):
        await escalation_service.draft_question("t1", "warranty")
    assert calls["drafts"] == []


# --- escalate ---


async def test_escalate_emails_the_department_then_escalates(monkeypatch) -> None:
    calls = _install(monkeypatch)

    result = await escalation_service.escalate("t1", "warranty", "  Is it covered?  ", "q1")

    assert result == "escalated-ticket"
    [(to, subject, body)] = calls["emails"]
    assert to == "warranty@example.com"
    assert "[T-1042]" in subject and "Kettle stopped heating" in subject
    assert body.startswith("Is it covered?")
    assert "Bought it in May" in body and "jo@example.com" not in body

    [(department_id, note, email)] = calls["escalated"]
    assert department_id == "warranty" and note == "Is it covered?"
    assert email == {
        "to": "warranty@example.com",
        "message_id": "<m1@example.com>",
        "question_draft_id": "q1",
        "edited": False,
    }


async def test_an_edited_question_is_recorded_as_edited(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await escalation_service.escalate("t1", "warranty", "Is it covered, and can we refund?", "q1")

    assert calls["escalated"][0][2]["edited"] is True


async def test_the_escalating_agent_is_recorded(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await escalation_service.escalate("t1", "warranty", "Is it covered?", "q1", "agent-1")

    assert calls["actors"] == ["agent-1"]


async def test_a_failed_email_leaves_the_ticket_unescalated(monkeypatch) -> None:
    calls = _install(monkeypatch, email_error=EmailSendError("connection refused"))

    with pytest.raises(EmailSendError):
        await escalation_service.escalate("t1", "warranty", "Is it covered?")
    assert calls["escalated"] == []


async def test_an_unknown_department_is_refused_before_any_email(monkeypatch) -> None:
    calls = _install(monkeypatch, department=None)

    with pytest.raises(UnknownDepartment):
        await escalation_service.escalate("t1", "nowhere", "Is it covered?")
    assert calls["emails"] == []


# --- record_answer ---


async def test_answer_is_saved_and_the_ticket_moves_to_dept_responded(monkeypatch) -> None:
    calls = _install(monkeypatch, ticket={**TICKET, "status": "escalated", "escalated_dept": "warranty"})

    result = await escalation_service.record_answer("t1", "  Replace it.  ")

    assert result == "responded-ticket"
    assert calls["responses"] == [{"ticket_id": "t1", "department_id": "warranty", "answer_text": "Replace it."}]
    assert calls["responded"][0]["id"] == "r1"
    # No agent given, as on the email path: the actor is the system.
    assert calls["actors"] == [None]


async def test_the_agent_who_pasted_the_answer_is_recorded(monkeypatch) -> None:
    calls = _install(monkeypatch, ticket={**TICKET, "status": "escalated", "escalated_dept": "warranty"})

    await escalation_service.record_answer("t1", "Replace it.", "agent-1")

    assert calls["actors"] == ["agent-1"]


async def test_answer_on_a_ticket_that_is_not_escalated_saves_nothing(monkeypatch) -> None:
    calls = _install(monkeypatch)

    with pytest.raises(IllegalTransition):
        await escalation_service.record_answer("t1", "Replace it.")
    assert calls["responses"] == [] and calls["responded"] == []


def test_an_answered_ticket_can_be_redrafted_and_come_back() -> None:
    from cms.services.ticket_service import assert_transition

    assert_transition("dept_responded", "processing")
    assert_transition("processing", "dept_responded")
    with pytest.raises(IllegalTransition):
        assert_transition("escalated", "processing")
