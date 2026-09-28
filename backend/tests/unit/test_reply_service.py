import pytest

from cms.services import reply_service
from cms.services.email_sender import EmailSendError
from cms.services.reply_service import DraftConflict, InvalidReply, strip_markers
from cms.services.ticket_service import IllegalTransition

TICKET = {
    "id": "t1",
    "ticket_no": 1042,
    "status": "drafted",
    "subject": "Kettle stopped heating",
    "customer_email": "jo@example.com",
    "severity": "normal",
    "source": "web",
    "created_at": "2026-09-27T10:00:00Z",
    "updated_at": "2026-09-27T10:00:00Z",
}
DRAFT = {
    "id": "d1",
    "ticket_id": "t1",
    "version": 2,
    "draft_text": "Dear customer,\n\nIt is covered [1][3].\n\nKind regards,\nCustomer Care",
    "no_match": False,
}


def _install(monkeypatch, ticket=None, draft=None, latest=None, feedback=None, email_error=None) -> dict:
    """Stub every read and write. Returns a dict recording what happened."""
    calls = {"feedback": [], "deleted": [], "events": [], "emails": [], "resolved": [], "actors": []}
    ticket = ticket or TICKET
    draft = draft or DRAFT

    async def fetch_ticket(ticket_id):
        return ticket

    async def fetch_draft(draft_id):
        return draft

    async def fetch_latest_draft(ticket_id, kind="customer_reply"):
        return latest or draft

    async def fetch_feedback(draft_id):
        return feedback

    async def insert_feedback(row):
        calls["feedback"].append(row)
        return {"id": "f1", **row}

    async def delete_feedback(feedback_id):
        calls["deleted"].append(feedback_id)

    async def append_event(ticket_id, event, payload=None, actor_id=None):
        calls["events"].append((event, payload))
        calls["actors"].append((event, actor_id))

    async def send_email(to, subject, body):
        calls["emails"].append((to, subject, body))
        if email_error:
            raise email_error
        return "<m1@example.com>"

    async def resolve_ticket(ticket_id, note=None, actor_id=None):
        calls["resolved"].append(ticket_id)
        calls["actors"].append(("resolved", actor_id))
        return "resolved-ticket"

    monkeypatch.setattr(reply_service.tickets, "fetch_ticket", fetch_ticket)
    monkeypatch.setattr(reply_service.drafts, "fetch_draft", fetch_draft)
    monkeypatch.setattr(reply_service.drafts, "fetch_latest_draft", fetch_latest_draft)
    monkeypatch.setattr(reply_service.draft_feedback, "fetch_feedback", fetch_feedback)
    monkeypatch.setattr(reply_service.draft_feedback, "insert_feedback", insert_feedback)
    monkeypatch.setattr(reply_service.draft_feedback, "delete_feedback", delete_feedback)
    monkeypatch.setattr(reply_service.ticket_events, "append_event", append_event)
    monkeypatch.setattr(reply_service, "send_email", send_email)
    monkeypatch.setattr(reply_service.ticket_service, "resolve_ticket", resolve_ticket)
    return calls


def test_strip_markers() -> None:
    assert strip_markers("It is covered [1][4].") == "It is covered."
    assert strip_markers("Covered. [7][1]\nNext [2] line") == "Covered.\nNext line"
    assert strip_markers("No markers here.") == "No markers here."


async def test_unedited_draft_is_sent_as_accepted(monkeypatch) -> None:
    calls = _install(monkeypatch)

    result = await reply_service.send_reply("t1", "d1", DRAFT["draft_text"])

    assert result == "resolved-ticket"
    [(to, subject, body)] = calls["emails"]
    assert to == "jo@example.com"
    assert subject == "Re: Kettle stopped heating [T-1042]"
    assert "[1]" not in body and "It is covered." in body
    assert calls["feedback"] == [
        {"draft_id": "d1", "user_id": None, "action": "accepted", "final_text": body}
    ]
    assert calls["events"] == [
        (
            "sent",
            {
                "draft_id": "d1",
                "version": 2,
                "action": "accepted",
                "message_id": "<m1@example.com>",
                "to": "jo@example.com",
            },
        )
    ]
    assert calls["resolved"] == ["t1"]


async def test_the_sending_agent_is_recorded(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await reply_service.send_reply("t1", "d1", DRAFT["draft_text"], "agent-1")

    assert calls["feedback"][0]["user_id"] == "agent-1"
    assert calls["actors"] == [("sent", "agent-1"), ("resolved", "agent-1")]


async def test_changed_text_is_sent_as_edited(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await reply_service.send_reply("t1", "d1", "Dear Jo,\n\nWe will replace it [1].")

    assert calls["feedback"][0]["action"] == "edited"
    assert calls["feedback"][0]["final_text"] == "Dear Jo,\n\nWe will replace it."


async def test_whitespace_changes_still_count_as_accepted(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await reply_service.send_reply("t1", "d1", DRAFT["draft_text"].replace("\n\n", "\n") + "  ")

    assert calls["feedback"][0]["action"] == "accepted"


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        ({"latest": {**DRAFT, "id": "d2"}}, DraftConflict),
        ({"feedback": {"id": "f0", "action": "rejected"}}, DraftConflict),
        ({"draft": {**DRAFT, "no_match": True}}, DraftConflict),
        ({"ticket": {**TICKET, "customer_email": None}}, InvalidReply),
        ({"ticket": {**TICKET, "status": "resolved"}}, IllegalTransition),
        ({"ticket": {**TICKET, "status": "escalated"}}, DraftConflict),
    ],
    ids=["stale", "already-handled", "unedited-holding-reply", "no-email", "closed-ticket", "escalated"],
)
async def test_refused_before_any_email(monkeypatch, setup, error) -> None:
    calls = _install(monkeypatch, **setup)

    with pytest.raises(error):
        await reply_service.send_reply("t1", "d1", DRAFT["draft_text"])

    assert calls["emails"] == [] and calls["feedback"] == []


async def test_edited_holding_reply_can_be_sent(monkeypatch) -> None:
    calls = _install(monkeypatch, draft={**DRAFT, "no_match": True})

    await reply_service.send_reply("t1", "d1", "Dear customer,\n\nWe have refunded you.")

    assert len(calls["emails"]) == 1


async def test_failed_email_frees_the_draft_and_is_recorded(monkeypatch) -> None:
    calls = _install(monkeypatch, email_error=EmailSendError("ConnectionRefusedError: down"))

    with pytest.raises(EmailSendError):
        await reply_service.send_reply("t1", "d1", DRAFT["draft_text"])

    assert calls["deleted"] == ["f1"]
    assert calls["events"] == [
        ("failed", {"stage": "send_email", "error": "ConnectionRefusedError: down"})
    ]
    assert calls["resolved"] == []


async def test_discard_is_refused_while_escalated(monkeypatch) -> None:
    calls = _install(monkeypatch, ticket={**TICKET, "status": "escalated"})

    with pytest.raises(DraftConflict):
        await reply_service.discard_draft("t1", "d1", "wrong_tone")

    assert calls["feedback"] == [] and calls["events"] == []


async def test_discard_records_a_rejection(monkeypatch) -> None:
    calls = _install(monkeypatch)

    ticket = await reply_service.discard_draft("t1", "d1", "wrong_tone", "too stiff")

    assert calls["feedback"] == [
        {"draft_id": "d1", "user_id": None, "action": "rejected", "edit_reason": "wrong_tone"}
    ]
    assert calls["events"] == [
        ("discarded", {"draft_id": "d1", "version": 2, "reason": "wrong_tone", "note": "too stiff"})
    ]
    assert calls["emails"] == [] and calls["resolved"] == []
    assert ticket.id == "t1"


async def test_the_discarding_agent_is_recorded(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await reply_service.discard_draft("t1", "d1", "wrong_tone", user_id="agent-1")

    assert calls["feedback"][0]["user_id"] == "agent-1"
    assert calls["actors"] == [("discarded", "agent-1")]
