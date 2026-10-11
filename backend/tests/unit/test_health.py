"""The probes and the admin health view: status codes, timeouts, and no error text in public."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from cms.api.deps import get_current_user
from cms.config.settings import get_settings
from cms.main import create_app
from cms.schemas.auth import CurrentUser
from cms.services import health_checks

ADMIN = CurrentUser(id="u2", email="admin@example.com", display_name="Ada", role="admin")
AGENT = CurrentUser(id="u1", email="a@example.com", display_name="Asha", role="agent")
SECRET = "http://user:hunter2@qdrant.internal:6333"


async def _fail() -> str:
    raise RuntimeError(f"could not reach {SECRET}")


@pytest.fixture
def checks(monkeypatch) -> dict:
    """Every check passes and records that it ran; tests swap in failures."""
    ran: dict = {}

    def recording(name: str):
        async def check() -> str:
            ran[name] = True
            return "ok"

        return check

    for name in list(health_checks.CHECKS):
        monkeypatch.setitem(health_checks.CHECKS, name, recording(name))
    return ran


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _as(user: CurrentUser) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_live_checks_nothing(client, checks) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert checks == {}


def test_ready_when_the_hard_dependencies_answer(client, checks) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "dependencies": {"supabase": "ok", "qdrant": "ok"}}


def test_ready_never_runs_the_soft_checks(client, checks) -> None:
    client.get("/health/ready")

    assert set(checks) == {"supabase", "qdrant"}


def test_a_hard_dependency_down_is_503_without_its_error(client, checks, monkeypatch) -> None:
    monkeypatch.setitem(health_checks.CHECKS, "qdrant", _fail)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "dependencies": {"supabase": "ok", "qdrant": "error"}}
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text


def test_a_soft_dependency_down_keeps_ready(client, checks, monkeypatch) -> None:
    monkeypatch.setitem(health_checks.CHECKS, "smtp", _fail)

    assert client.get("/health/ready").status_code == 200


async def test_a_slow_check_times_out(checks, monkeypatch) -> None:
    async def hang() -> str:
        await asyncio.sleep(5)
        return "ok"

    monkeypatch.setitem(health_checks.CHECKS, "qdrant", hang)
    monkeypatch.setattr(get_settings(), "health_check_timeout_seconds", 0.01)

    results = await health_checks.check_dependencies(["qdrant"])

    assert results["qdrant"].status == "error"
    assert results["qdrant"].detail == "timed out"


async def test_mongo_is_disabled_with_chat_memory_off(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "chat_memory_enabled", False)

    results = await health_checks.check_dependencies(["mongo"])

    assert results["mongo"].status == "disabled"


def test_admin_health_names_the_error_type_only(checks, monkeypatch) -> None:
    monkeypatch.setitem(health_checks.CHECKS, "openrouter", _fail)

    response = _as(ADMIN).get("/api/v1/admin/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert set(body["dependencies"]) == {"supabase", "qdrant", "mongo", "openrouter", "smtp"}
    assert body["dependencies"]["openrouter"] == {"status": "error", "detail": "RuntimeError"}
    assert body["dependencies"]["smtp"] == {"status": "ok", "detail": None}
    assert "hunter2" not in response.text


def test_admin_health_is_admins_only(checks) -> None:
    assert _as(AGENT).get("/api/v1/admin/health").status_code == 403
