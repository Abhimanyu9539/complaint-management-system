"""Deleting a stored conversation from the checkpointer."""

from types import SimpleNamespace

import pytest

from cms.services import chat_service


async def test_the_thread_is_deleted_by_session_id(monkeypatch) -> None:
    calls: list[str] = []

    async def adelete_thread(thread_id):
        calls.append(thread_id)

    monkeypatch.setattr(
        chat_service, "get_checkpointer", lambda: SimpleNamespace(adelete_thread=adelete_thread)
    )
    await chat_service.delete_session("s-1")

    assert calls == ["s-1"]


async def test_a_failed_delete_is_raised(monkeypatch) -> None:
    async def adelete_thread(thread_id):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(
        chat_service, "get_checkpointer", lambda: SimpleNamespace(adelete_thread=adelete_thread)
    )
    with pytest.raises(RuntimeError):
        await chat_service.delete_session("s-1")
