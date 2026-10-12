from fastapi import FastAPI
from fastapi.testclient import TestClient

from cms.api.middleware import RequestIdMiddleware
from cms.observability.context import request_id_var

HEADER = "X-Request-ID"


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/echo")
    async def echo() -> dict:
        # What every log line written while handling the request would carry.
        return {"request_id": request_id_var.get()}

    app.add_middleware(RequestIdMiddleware)
    return TestClient(app)


def test_a_valid_incoming_id_is_kept_and_echoed() -> None:
    response = _client().get("/echo", headers={HEADER: "n8n-run-42"})

    assert response.headers[HEADER] == "n8n-run-42"
    assert response.json() == {"request_id": "n8n-run-42"}


def test_a_missing_id_is_generated() -> None:
    response = _client().get("/echo")

    request_id = response.headers[HEADER]
    assert len(request_id) == 32
    assert response.json() == {"request_id": request_id}


def test_an_unsafe_id_is_replaced() -> None:
    response = _client().get("/echo", headers={HEADER: "bad id\twith tab"})

    assert response.headers[HEADER] != "bad id\twith tab"
    assert len(response.headers[HEADER]) == 32


def test_the_id_is_cleared_after_the_request() -> None:
    _client().get("/echo")

    assert request_id_var.get() is None
