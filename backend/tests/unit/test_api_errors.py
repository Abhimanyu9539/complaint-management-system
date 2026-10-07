"""How service errors reach the browser: status code, `detail`, and CORS headers on a 503."""

import pytest
from fastapi.testclient import TestClient

from cms.api.deps import get_current_user
from cms.api.v1.routes import tickets as ticket_routes
from cms.config.settings import get_settings
from cms.db.repositories import NotFound
from cms.main import create_app
from cms.schemas.auth import CurrentUser
from cms.services.email_sender import EmailSendError
from cms.services.ticket_service import IllegalTransition

AGENT = CurrentUser(id="u1", email="a@example.com", display_name="Asha", role="agent")
ORIGIN = "http://localhost:5173"


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AGENT
    return TestClient(app)


def _raise(exc: Exception):
    async def fail(*args, **kwargs):
        raise exc

    return fail


def test_not_found_is_404_with_its_message(client, monkeypatch) -> None:
    monkeypatch.setattr(ticket_routes.ticket_service, "get_ticket", _raise(NotFound("No ticket with id t9")))

    response = client.get("/api/v1/tickets/t9")

    assert response.status_code == 404
    assert response.json() == {"detail": "No ticket with id t9"}


def test_illegal_transition_is_409(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ticket_routes.ticket_service, "resolve_ticket", _raise(IllegalTransition("resolved", "resolved"))
    )

    response = client.post("/api/v1/tickets/t1/resolve", json={})

    assert response.status_code == 409
    assert response.json() == {"detail": "A ticket at 'resolved' cannot move to 'resolved'."}


def test_failed_email_is_502_without_smtp_details(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ticket_routes.reply_service, "send_reply", _raise(EmailSendError("SMTPAuthenticationError: 535"))
    )

    response = client.post("/api/v1/tickets/t1/send", json={"draft_id": "d1", "final_text": "Hello"})

    assert response.status_code == 502
    assert response.json() == {"detail": get_settings().email_send_failed_message}


def test_unexpected_error_is_503_and_keeps_cors(client, monkeypatch) -> None:
    monkeypatch.setattr(ticket_routes.ticket_service, "build_ticket_page", _raise(RuntimeError("db down")))

    response = client.get("/api/v1/tickets", headers={"Origin": ORIGIN})

    assert response.status_code == 503
    assert response.json() == {"detail": get_settings().api_unavailable_message}
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_a_key_error_is_not_a_404(client, monkeypatch) -> None:
    monkeypatch.setattr(ticket_routes.ticket_service, "get_ticket", _raise(KeyError("status")))

    assert client.get("/api/v1/tickets/t1").status_code == 503


def test_dept_question_failure_has_its_own_message(client, monkeypatch) -> None:
    monkeypatch.setattr(ticket_routes.escalation_service, "draft_question", _raise(RuntimeError("model")))

    response = client.post("/api/v1/tickets/t1/dept-question", json={"department_id": "billing"})

    assert response.status_code == 503
    assert response.json() == {"detail": get_settings().dept_question_failed_message}


def test_dept_question_still_maps_domain_errors(client, monkeypatch) -> None:
    monkeypatch.setattr(ticket_routes.escalation_service, "draft_question", _raise(NotFound("No ticket")))

    response = client.post("/api/v1/tickets/t1/dept-question", json={"department_id": "billing"})

    assert response.status_code == 404


def test_customer_form_failure_tells_them_the_text_is_safe(client, monkeypatch) -> None:
    monkeypatch.setattr(ticket_routes.ticket_service, "create_ticket", _raise(RuntimeError("db down")))

    response = client.post(
        "/api/v1/tickets",
        json={"subject": "Kettle broke", "body": "It stopped heating.", "customer_email": "jo@example.com"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": get_settings().ticket_create_failed_message}
