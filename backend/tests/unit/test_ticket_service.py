import pytest

from cms.db.repositories import NotFound
from cms.services import ticket_service


def _install(monkeypatch, status: str, moved_by_someone_else: bool = False) -> list:
    """A ticket at `status`. The update fails as if another request moved it first."""
    updates = []

    async def fetch_ticket(ticket_id):
        return {"id": ticket_id, "status": status}

    async def update_ticket(ticket_id, patch, expected_status=None):
        updates.append((patch, expected_status))
        if moved_by_someone_else:
            raise NotFound("no row at that status")
        return {"id": ticket_id, **patch}

    monkeypatch.setattr(ticket_service.tickets, "fetch_ticket", fetch_ticket)
    monkeypatch.setattr(ticket_service.tickets, "update_ticket", update_ticket)
    return updates


async def test_the_update_only_applies_at_the_status_that_was_read(monkeypatch) -> None:
    updates = _install(monkeypatch, "drafted")

    await ticket_service.start_processing("t1", resume=False)

    [(patch, expected_status)] = updates
    assert patch["status"] == "processing"
    assert expected_status == "drafted"


async def test_a_ticket_moved_by_another_request_is_a_status_changed(monkeypatch) -> None:
    _install(monkeypatch, "drafted", moved_by_someone_else=True)

    with pytest.raises(ticket_service.StatusChanged):
        await ticket_service.start_processing("t1", resume=False)
