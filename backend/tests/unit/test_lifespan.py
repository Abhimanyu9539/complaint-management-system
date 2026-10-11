"""Startup loads the models (or refuses to start); shutdown closes every client."""

import pytest
from fastapi.testclient import TestClient

from cms import lifespan
from cms.config.settings import get_settings
from cms.main import create_app

LOADERS = (
    "get_sparse_embeddings",
    "get_case_scrubber",
    "get_input_guard",
    "get_output_guard",
    "get_lookup_guard",
)


@pytest.fixture
def calls(monkeypatch) -> list[str]:
    """Stub every loader and closer so nothing real is loaded or closed; record the calls."""
    recorded: list[str] = []

    def loader(name: str):
        def load() -> None:
            recorded.append(name)

        load.__name__ = name
        return load

    def closer(name: str):
        async def close() -> None:
            recorded.append(name)

        close.__name__ = name
        return close

    for name in LOADERS:
        monkeypatch.setattr(lifespan, name, loader(name))
    monkeypatch.setattr(lifespan, "CLOSERS", (closer("qdrant"), closer("supabase"), closer("mongo")))
    monkeypatch.setattr(get_settings(), "warm_up_on_startup", True)
    monkeypatch.setattr(get_settings(), "guardrails_enabled", True)
    return recorded


def test_startup_loads_every_model_and_shutdown_closes_every_client(calls) -> None:
    with TestClient(create_app()):
        assert calls == list(LOADERS)

    assert calls[len(LOADERS) :] == ["qdrant", "supabase", "mongo"]


def test_guardrails_off_loads_only_bm25_and_the_case_scrubber(calls, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "guardrails_enabled", False)

    with TestClient(create_app()):
        assert calls == ["get_sparse_embeddings", "get_case_scrubber"]


def test_a_failed_load_stops_startup(calls, monkeypatch) -> None:
    def broken() -> None:
        raise OSError("Can't find model 'en_core_web_lg'")

    monkeypatch.setattr(lifespan, "get_input_guard", broken)

    with pytest.raises(OSError, match="en_core_web_lg"), TestClient(create_app()):
        pass


def test_warm_up_off_loads_nothing(calls, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "warm_up_on_startup", False)

    with TestClient(create_app()):
        assert calls == []


def test_one_failed_close_does_not_skip_the_rest(calls, monkeypatch) -> None:
    async def broken() -> None:
        raise RuntimeError("already closed")

    async def mongo() -> None:
        calls.append("mongo")

    monkeypatch.setattr(lifespan, "CLOSERS", (broken, mongo))

    with TestClient(create_app()):
        pass

    assert calls[-1] == "mongo"
