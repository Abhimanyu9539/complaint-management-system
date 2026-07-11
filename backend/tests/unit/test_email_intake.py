import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cms.api.v1.routes import emails
from cms.config.settings import get_settings
from cms.schemas.emails import InboundEmailRequest, InboundEmailResult
from cms.schemas.tickets import TicketCreated
from cms.services import email_intake, ticket_service

TICKET = {
    "id": "t1",
    "ticket_no": 1042,
    "status": "escalated",
    "escalated_dept": "warranty",
    "customer_email": "jo@example.com",
}
DEPARTMENT = {"id": "warranty", "name": "Warranty", "mailbox": "warranty@example.com"}
QUOTED = "Replace it under warranty.\n\nOn Mon, 5 Oct 2026, Customer Care wrote:\n> Is it covered?"


def _email(**overrides) -> InboundEmailRequest:
    fields = {
        "message_id": "<m1@example.com>",
        "from_address": "Jo Bloggs <Jo@Example.com>",
        "subject": "My kettle stopped heating",
        "text": "It stopped after two weeks.",
    }
    return InboundEmailRequest(**{**fields, **overrides})


def _install(monkeypatch, ticket=TICKET, duplicate=False, error=None) -> dict:
    """Stub every read and write. Returns a dict recording what happened."""
    calls = {"claimed": [], "finished": [], "created": [], "answers": [], "processing": [], "replies": []}

    async def claim_email(row):
        calls["claimed"].append(row)
        return None if duplicate else "e1"

    async def finish_email(email_id, outcome, reason=None, ticket_id=None):
        calls["finished"].append((outcome, reason, ticket_id))

    async def fetch_department_by_mailbox(address):
        return DEPARTMENT if address == DEPARTMENT["mailbox"] else None

    async def fetch_ticket_by_no(ticket_no):
        if ticket is None:
            raise LookupError(ticket_no)
        return ticket

    async def create_ticket(**kwargs):
        if error:
            raise error
        calls["created"].append(kwargs)
        return TicketCreated(id="t9", ticket_no=1050, status="new", created_at="2026-10-04T10:00:00Z")

    async def record_answer(ticket_id, answer_text):
        calls["answers"].append((ticket_id, answer_text))

    async def start_processing(ticket_id, resume=True):
        calls["processing"].append((ticket_id, resume))

    async def record_customer_reply(ticket_id, text):
        calls["replies"].append((ticket_id, text))

    monkeypatch.setattr(email_intake.inbound_emails, "claim_email", claim_email)
    monkeypatch.setattr(email_intake.inbound_emails, "finish_email", finish_email)
    monkeypatch.setattr(email_intake.departments, "fetch_department_by_mailbox", fetch_department_by_mailbox)
    monkeypatch.setattr(email_intake.tickets, "fetch_ticket_by_no", fetch_ticket_by_no)
    monkeypatch.setattr(email_intake.ticket_service, "create_ticket", create_ticket)
    monkeypatch.setattr(email_intake.escalation_service, "record_answer", record_answer)
    monkeypatch.setattr(email_intake.ticket_service, "start_processing", start_processing)
    monkeypatch.setattr(email_intake.ticket_service, "record_customer_reply", record_customer_reply)
    return calls


# --- ingest_email ---


async def test_a_new_complaint_opens_an_email_ticket(monkeypatch) -> None:
    calls = _install(monkeypatch)

    result, trigger = await email_intake.ingest_email(_email())

    assert result.outcome == "created" and result.ticket_no == 1050 and trigger == "created"
    [created] = calls["created"]
    assert created["source"] == "email" and created["customer_email"] == "jo@example.com"
    assert created["subject"] == "My kettle stopped heating"
    assert calls["claimed"][0]["from_address"] == "jo@example.com"
    assert calls["finished"] == [("created", None, "t9")]


async def test_a_department_reply_records_the_answer_without_the_quote(monkeypatch) -> None:
    calls = _install(monkeypatch)

    result, trigger = await email_intake.ingest_email(
        _email(from_address="warranty@example.com", subject="Re: [T-1042] Question", text=QUOTED)
    )

    assert result.outcome == "dept_answer" and trigger == "dept_response"
    assert calls["answers"] == [("t1", "Replace it under warranty.")]
    assert calls["processing"] == [("t1", False)]


async def test_a_department_reply_to_a_ticket_not_waiting_on_it_is_ignored(monkeypatch) -> None:
    calls = _install(monkeypatch, ticket={**TICKET, "status": "drafted"})

    result, trigger = await email_intake.ingest_email(
        _email(from_address="warranty@example.com", subject="Re: [T-1042] Question", text=QUOTED)
    )

    assert result.outcome == "ignored" and trigger is None
    assert result.reason == "ticket isn't waiting on this department"
    assert calls["answers"] == [] and calls["finished"][0][2] == "t1"


async def test_a_customer_reply_is_recorded_on_the_ticket(monkeypatch) -> None:
    calls = _install(monkeypatch)

    result, trigger = await email_intake.ingest_email(_email(subject="Re: Kettle [T-1042]", text=QUOTED))

    assert result.outcome == "customer_reply" and trigger is None
    assert calls["replies"] == [("t1", "Replace it under warranty.")]


@pytest.mark.parametrize(
    ("overrides", "ticket", "reason"),
    [
        ({"subject": "Re: [T-7] Kettle"}, None, "no ticket T-7"),
        ({"from_address": "someone@else.com", "subject": "Re: [T-1042]"}, TICKET, "sender is neither"),
        ({"from_address": "Customer Care <support@example.com>"}, TICKET, "our own address"),
        ({"auto_submitted": "auto-replied"}, TICKET, "automatic reply"),
        ({"from_address": "warranty@example.com"}, TICKET, "without a ticket reference"),
    ],
)
async def test_emails_that_fit_no_case_are_ignored_with_a_reason(monkeypatch, overrides, ticket, reason) -> None:
    calls = _install(monkeypatch, ticket=ticket)

    result, trigger = await email_intake.ingest_email(_email(**overrides))

    assert result.outcome == "ignored" and reason in result.reason and trigger is None
    assert calls["created"] == [] and calls["answers"] == [] and calls["replies"] == []
    assert calls["finished"][0][0] == "ignored"


async def test_a_duplicate_changes_nothing(monkeypatch) -> None:
    calls = _install(monkeypatch, duplicate=True)

    result, trigger = await email_intake.ingest_email(_email())

    assert result.outcome == "duplicate" and trigger is None
    assert calls["created"] == [] and calls["finished"] == []


async def test_a_failure_is_recorded_and_re_raised(monkeypatch) -> None:
    calls = _install(monkeypatch, error=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        await email_intake.ingest_email(_email())

    [(outcome, reason, _)] = calls["finished"]
    assert outcome == "ignored" and "db down" in reason


# --- reply_text ---


@pytest.mark.parametrize(
    "quote",
    [
        "On Mon, 5 Oct 2026 at 10:00, Customer Care <support@example.com> wrote:",
        "> Is it covered?",
        "-----Original Message-----",
        "From: Customer Care <support@example.com>",
    ],
)
def test_reply_text_stops_at_each_quote_marker(quote) -> None:
    assert email_intake.reply_text(f"Yes, replace it.\n\n{quote}\nOlder text") == "Yes, replace it."


def test_reply_text_keeps_a_body_with_no_quote() -> None:
    assert email_intake.reply_text("  Line one.\nLine two.  ") == "Line one.\nLine two."


# --- ticket_service.record_customer_reply ---


def _install_ticket(monkeypatch, status) -> dict:
    calls = {"events": [], "updates": []}

    async def fetch_ticket(ticket_id):
        return {"id": ticket_id, "status": status}

    async def append_event(ticket_id, event, payload=None, actor_id=None):
        calls["events"].append((event, payload))

    async def update_ticket(ticket_id, patch):
        calls["updates"].append(patch)

    monkeypatch.setattr(ticket_service.tickets, "fetch_ticket", fetch_ticket)
    monkeypatch.setattr(ticket_service.ticket_events, "append_event", append_event)
    monkeypatch.setattr(ticket_service.tickets, "update_ticket", update_ticket)
    return calls


async def test_a_reply_reopens_a_resolved_ticket_for_review(monkeypatch) -> None:
    calls = _install_ticket(monkeypatch, "resolved")

    await ticket_service.record_customer_reply("t1", "It broke again.")

    [patch] = calls["updates"]
    assert patch["status"] == "needs_review"
    assert patch["review_reasons"] == ["Customer replied after resolution."]
    assert [event for event, _ in calls["events"]] == ["customer_replied", "reopened"]
    assert calls["events"][0][1] == {"text": "It broke again."}


async def test_a_reply_on_an_open_ticket_is_only_recorded(monkeypatch) -> None:
    calls = _install_ticket(monkeypatch, "drafted")

    await ticket_service.record_customer_reply("t1", "Any news?")

    assert calls["updates"] == []
    assert [event for event, _ in calls["events"]] == ["customer_replied"]


# --- POST /emails/inbound ---


def _client(monkeypatch, secret) -> TestClient:
    async def ingest_email(email):
        return InboundEmailResult(outcome="ignored", reason="stub"), None

    monkeypatch.setattr(get_settings(), "inbound_email_secret", secret)
    monkeypatch.setattr(emails.email_intake, "ingest_email", ingest_email)
    app = FastAPI()
    app.include_router(emails.router)
    return TestClient(app)


BODY = {"message_id": "<m1@example.com>", "from_address": "jo@example.com", "subject": "Hi", "text": "Hello"}


def test_a_wrong_secret_is_refused(monkeypatch) -> None:
    response = _client(monkeypatch, "s3cret").post(
        "/emails/inbound", json=BODY, headers={"X-Inbound-Secret": "wrong"}
    )
    assert response.status_code == 401


def test_inbound_email_is_off_without_a_secret(monkeypatch) -> None:
    response = _client(monkeypatch, None).post(
        "/emails/inbound", json=BODY, headers={"X-Inbound-Secret": "anything"}
    )
    assert response.status_code == 503


def test_the_right_secret_files_the_email(monkeypatch) -> None:
    response = _client(monkeypatch, "s3cret").post(
        "/emails/inbound", json=BODY, headers={"X-Inbound-Secret": "s3cret"}
    )
    assert response.status_code == 200 and response.json()["outcome"] == "ignored"
