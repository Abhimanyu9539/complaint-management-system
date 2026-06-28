import pytest

from cms.config.settings import get_settings
from cms.ingestion.extract.cases_extractor import build_case_text
from cms.services import case_minting

TICKET = {
    "id": "t1",
    "ticket_no": 1042,
    "status": "resolved",
    "subject": "Kettle stopped heating",
    "body": "I'm Priya Sharma. My kettle from order ORD-5521 (invoice INV-88) stopped heating.",
    "escalated_dept": "warranty",
    "predicted_dept": "tech_support",
    "category": "faulty_product",
    "resolution_path": "escalated",
    "entities": {"order_no": "ORD-5521", "invoice_no": "INV-88"},
}
REPLY = "Dear Priya Sharma, we will replace the kettle from order ORD-5521 at no cost."
SENT = {"draft_id": "d2", "action": "edited", "final_text": REPLY}
# Newest first, as the repository returns them.
RESPONSES = [
    {"answer_text": "Approve a replacement."},
    {"answer_text": "Confirmed it is within warranty."},
]
SUMMARY = "Confirmed the kettle was within warranty. Issued a free replacement."


def _install(
    monkeypatch,
    ticket=None,
    feedback=SENT,
    summary=SUMMARY,
    summary_error=None,
    scrub_error=None,
) -> dict:
    """Stub every read, write, the model and the scrubber. Returns a dict recording what happened."""
    calls = {"summarised": [], "upserts": [], "ingested": [], "events": []}

    async def fetch_ticket(ticket_id):
        return ticket or TICKET

    async def fetch_latest_draft(ticket_id, kind="customer_reply"):
        return {"id": "d2", "version": 2}

    async def fetch_feedback(draft_id):
        return feedback

    async def list_responses(ticket_id):
        return RESPONSES

    async def scrub_case_text(text):
        if scrub_error:
            raise scrub_error
        return text.replace("Priya Sharma", "<PERSON>")

    async def summarise(complaint, guidance, reply):
        calls["summarised"].append((complaint, guidance, reply))
        if summary_error:
            raise summary_error
        return summary

    async def upsert_flywheel_case(row):
        calls["upserts"].append(row)
        return "c1"

    async def ingest_case(case_id, raw_text):
        calls["ingested"].append((case_id, raw_text))

    async def append_event(ticket_id, event, payload=None, actor_id=None):
        calls["events"].append((event, payload))

    monkeypatch.setattr(case_minting.tickets, "fetch_ticket", fetch_ticket)
    monkeypatch.setattr(case_minting.drafts, "fetch_latest_draft", fetch_latest_draft)
    monkeypatch.setattr(case_minting.draft_feedback, "fetch_feedback", fetch_feedback)
    monkeypatch.setattr(case_minting.dept_responses, "list_responses", list_responses)
    monkeypatch.setattr(case_minting, "scrub_case_text", scrub_case_text)
    monkeypatch.setattr(case_minting, "_summarise_resolution", summarise)
    monkeypatch.setattr(case_minting.cases, "upsert_flywheel_case", upsert_flywheel_case)
    monkeypatch.setattr(case_minting, "ingest_case", ingest_case)
    monkeypatch.setattr(case_minting.ticket_events, "append_event", append_event)
    monkeypatch.setattr(get_settings(), "flywheel_enabled", True)
    return calls


async def test_a_sent_escalated_ticket_mints_a_scrubbed_case(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await case_minting.mint_case("t1")

    [row] = calls["upserts"]
    assert row["ticket_id"] == "t1" and row["source"] == "flywheel"
    assert row["department_id"] == "warranty"
    assert row["title"] == "T-1042 — warranty / faulty_product"
    assert row["dept_guidance"] == "Confirmed it is within warranty.\n\nApprove a replacement."
    assert row["resolution_text"] == SUMMARY
    assert row["resolution_path"] == "escalated"
    assert "<PERSON>" in row["complaint_text"] and "Priya" not in row["complaint_text"]

    [(complaint, guidance, reply)] = calls["summarised"]
    assert "Priya" not in complaint + guidance + reply

    assert calls["ingested"] == [("c1", build_case_text(row))]
    [(event, payload)] = calls["events"]
    assert event == "case_minted"
    assert payload["case_id"] == "c1" and payload["fallback"] is False
    assert payload["prompt_version"] == get_settings().case_resolution_prompt_version


async def test_order_and_invoice_numbers_are_masked(monkeypatch) -> None:
    calls = _install(monkeypatch)

    await case_minting.mint_case("t1")

    [(complaint, _guidance, reply)] = calls["summarised"]
    assert "<ORDER_NO>" in complaint and "<INVOICE_NO>" in complaint and "<ORDER_NO>" in reply
    assert "ORD-5521" not in complaint + reply and "INV-88" not in complaint


async def test_a_direct_ticket_takes_the_predicted_department(monkeypatch) -> None:
    calls = _install(monkeypatch, ticket={**TICKET, "escalated_dept": None, "resolution_path": "direct"})

    await case_minting.mint_case("t1")

    [row] = calls["upserts"]
    assert row["department_id"] == "tech_support" and row["resolution_path"] == "direct"


@pytest.mark.parametrize(
    ("enabled", "ticket", "feedback"),
    [
        (False, TICKET, SENT),
        (True, {**TICKET, "status": "needs_review"}, SENT),
        (True, TICKET, {"draft_id": "d2", "action": "rejected", "final_text": None}),
        (True, TICKET, None),
    ],
    ids=["flywheel-off", "not-resolved", "draft-rejected", "no-feedback"],
)
async def test_nothing_is_minted_without_a_sent_reply(monkeypatch, enabled, ticket, feedback) -> None:
    calls = _install(monkeypatch, ticket=ticket, feedback=feedback)
    monkeypatch.setattr(get_settings(), "flywheel_enabled", enabled)

    await case_minting.mint_case("t1")

    assert calls["upserts"] == [] and calls["ingested"] == [] and calls["events"] == []


async def test_a_summary_with_an_unsupported_figure_falls_back_to_the_reply(monkeypatch) -> None:
    calls = _install(monkeypatch, summary="Refunded ₹9,999 within 30 days.")

    await case_minting.mint_case("t1")

    [row] = calls["upserts"]
    assert row["resolution_text"] == "Dear <PERSON>, we will replace the kettle from order <ORDER_NO> at no cost."
    [(_event, payload)] = calls["events"]
    assert payload["fallback"] is True


async def test_a_failed_summary_call_falls_back_to_the_reply(monkeypatch) -> None:
    calls = _install(monkeypatch, summary_error=RuntimeError("model down"))

    await case_minting.mint_case("t1")

    [row] = calls["upserts"]
    assert row["resolution_text"].startswith("Dear <PERSON>")
    [(event, payload)] = calls["events"]
    assert event == "case_minted" and payload["fallback"] is True


async def test_a_failed_scrub_stores_nothing_and_records_a_failed_event(monkeypatch) -> None:
    calls = _install(monkeypatch, scrub_error=RuntimeError("presidio down"))

    await case_minting.mint_case("t1")

    assert calls["upserts"] == [] and calls["ingested"] == [] and calls["summarised"] == []
    [(event, payload)] = calls["events"]
    assert event == "failed" and payload["stage"] == "mint_case"
    assert "presidio down" in payload["error"]
