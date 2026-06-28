import pytest

from cms.cli import delete_case

TICKET = {"id": "t1", "ticket_no": 14}
FLYWHEEL_CASE = {"id": "c1", "title": "T-14 — warranty / faulty_product", "source": "flywheel", "status": "indexed"}


def _install(monkeypatch, case=FLYWHEEL_CASE) -> list:
    """Stub the reads and every delete step. Returns the steps in the order they ran."""
    steps: list = []

    async def fetch_ticket_by_no(ticket_no):
        return TICKET

    async def fetch_case_by_ticket(ticket_id):
        return case

    async def mark_case_deleting(case_id):
        steps.append(("deleting", case_id))

    async def existing_point_ids(collection, document_id):
        return {"p1", "p2"}

    async def delete_stale_points(collection, document_id, stale_ids):
        steps.append(("points", sorted(stale_ids)))

    async def delete_row(case_id):
        steps.append(("row", case_id))

    async def append_event(ticket_id, event, payload=None, actor_id=None):
        steps.append((event, payload))

    monkeypatch.setattr(delete_case.tickets, "fetch_ticket_by_no", fetch_ticket_by_no)
    monkeypatch.setattr(delete_case.cases, "fetch_case_by_ticket", fetch_case_by_ticket)
    monkeypatch.setattr(delete_case.cases, "mark_case_deleting", mark_case_deleting)
    monkeypatch.setattr(delete_case, "existing_point_ids", existing_point_ids)
    monkeypatch.setattr(delete_case, "delete_stale_points", delete_stale_points)
    monkeypatch.setattr(delete_case.cases, "delete_case", delete_row)
    monkeypatch.setattr(delete_case.ticket_events, "append_event", append_event)
    return steps


@pytest.mark.parametrize(("value", "expected"), [("T-14", 14), ("t-14", 14), ("14", 14)])
def test_ticket_reference_is_parsed(value: str, expected: int) -> None:
    assert delete_case.parse_ticket_no(value) == expected


async def test_points_are_removed_before_the_row(monkeypatch) -> None:
    steps = _install(monkeypatch)

    removed = await delete_case.delete_ticket_case(14)

    assert [step[0] for step in steps] == ["deleting", "points", "row", "case_removed"]
    assert steps[1] == ("points", ["p1", "p2"])
    assert steps[3][1] == {"case_id": "c1", "title": FLYWHEEL_CASE["title"]}
    assert removed["points"] == 2


async def test_a_seed_case_is_refused(monkeypatch) -> None:
    steps = _install(monkeypatch, case={**FLYWHEEL_CASE, "source": "seed"})

    with pytest.raises(ValueError):
        await delete_case.delete_ticket_case(14)
    assert steps == []


async def test_a_ticket_with_no_case_is_refused(monkeypatch) -> None:
    steps = _install(monkeypatch, case=None)

    with pytest.raises(LookupError):
        await delete_case.delete_ticket_case(14)
    assert steps == []
