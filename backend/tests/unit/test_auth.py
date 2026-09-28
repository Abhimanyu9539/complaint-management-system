"""Who may call the API: token verification, the profile check, and which routes are guarded."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from cms.api import deps
from cms.api.v1.router import api_router
from cms.api.v1.routes import tickets as ticket_routes
from cms.config.settings import get_settings
from cms.schemas.tickets import TicketCreated

KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())

AGENT = {"id": "u1", "email": "a@example.com", "display_name": "Asha", "role": "agent", "is_active": True}
ADMIN = {**AGENT, "id": "u2", "role": "admin"}


def _token(key=KEY, **overrides) -> str:
    settings = get_settings()
    claims = {
        "sub": "u1",
        "aud": settings.supabase_jwt_audience,
        "iss": settings.supabase_jwt_issuer,
        "exp": int(time.time()) + 3600,
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "k1"})


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def signed_in(monkeypatch):
    """Stub the signing keys with KEY's public half, and the profile read. Returns the profile store."""
    profiles: dict[str, dict | Exception] = {"u1": AGENT, "u2": ADMIN}

    client = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=KEY.public_key()))
    monkeypatch.setattr(deps, "_jwk_client", lambda: client)

    async def fetch_profile(user_id):
        profile = profiles.get(user_id)
        if profile is None:
            raise LookupError(user_id)
        if isinstance(profile, Exception):
            raise profile
        return profile

    monkeypatch.setattr(deps.profiles, "fetch_profile", fetch_profile)
    return profiles


async def _status(credentials) -> int:
    with pytest.raises(HTTPException) as caught:
        await deps.get_current_user(credentials)
    return caught.value.status_code


# --- get_current_user ---


async def test_a_valid_token_gives_the_profile(signed_in) -> None:
    user = await deps.get_current_user(_bearer(_token()))

    assert user.id == "u1" and user.role == "agent" and user.display_name == "Asha"


async def test_no_token_is_401_with_a_bearer_challenge(signed_in) -> None:
    with pytest.raises(HTTPException) as caught:
        await deps.get_current_user(None)

    assert caught.value.status_code == 401
    assert caught.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_a_token_issued_a_moment_ahead_of_our_clock_is_accepted(signed_in) -> None:
    """Supabase's clock can run a second or two ahead; a fresh token must not fail on `iat`."""
    user = await deps.get_current_user(_bearer(_token(iat=int(time.time()) + 3)))

    assert user.id == "u1"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: _token(key=OTHER_KEY), id="wrong signature"),
        pytest.param(lambda: _token(exp=int(time.time()) - 120), id="expired"),
        pytest.param(lambda: _token(iat=int(time.time()) + 600), id="issued in the future"),
        pytest.param(lambda: _token(aud="anon"), id="wrong audience"),
        pytest.param(lambda: _token(iss="https://elsewhere.supabase.co/auth/v1"), id="wrong issuer"),
        pytest.param(lambda: "not-a-jwt", id="garbage"),
    ],
)
async def test_a_bad_token_is_401(signed_in, token) -> None:
    assert await _status(_bearer(token())) == 401


async def test_a_user_without_a_profile_is_403(signed_in) -> None:
    assert await _status(_bearer(_token(sub="stranger"))) == 403


async def test_an_inactive_user_is_403(signed_in) -> None:
    signed_in["u1"] = {**AGENT, "is_active": False}

    assert await _status(_bearer(_token())) == 403


async def test_a_failed_profile_read_is_503(signed_in) -> None:
    signed_in["u1"] = RuntimeError("supabase down")

    assert await _status(_bearer(_token())) == 503


async def test_unreachable_signing_keys_are_503(signed_in, monkeypatch) -> None:
    def refuse(token):
        raise jwt.PyJWKClientConnectionError("no route to host")

    monkeypatch.setattr(deps, "_jwk_client", lambda: SimpleNamespace(get_signing_key_from_jwt=refuse))

    assert await _status(_bearer(_token())) == 503


# --- require_admin ---


async def test_an_agent_is_refused_an_admin_route(signed_in) -> None:
    agent = await deps.get_current_user(_bearer(_token()))

    with pytest.raises(HTTPException) as caught:
        await deps.require_admin(agent)
    assert caught.value.status_code == 403


async def test_an_admin_passes(signed_in) -> None:
    admin = await deps.get_current_user(_bearer(_token(sub="u2")))

    assert (await deps.require_admin(admin)).role == "admin"


# --- which routes are guarded ---


@pytest.fixture
def client(signed_in, monkeypatch) -> TestClient:
    """The real v1 router, with the ticket insert and the background run stubbed."""

    async def create_ticket(**kwargs):
        return TicketCreated(id="t1", ticket_no=1, status="new", created_at="2026-10-04T00:00:00Z")

    async def process_ticket(*args):
        return None

    monkeypatch.setattr(ticket_routes.ticket_service, "create_ticket", create_ticket)
    monkeypatch.setattr(ticket_routes.ticket_pipeline, "process_ticket", process_ticket)
    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app)


def _auth(sub: str) -> dict:
    return {"Authorization": f"Bearer {_token(sub=sub)}"}


def test_the_ticket_queue_needs_a_token(client) -> None:
    assert client.get("/api/v1/tickets").status_code == 401


def test_admin_routes_need_an_admin(client) -> None:
    assert client.get("/api/v1/admin/overview").status_code == 401
    assert client.get("/api/v1/admin/overview", headers=_auth("u1")).status_code == 403


def test_me_returns_the_signed_in_user(client) -> None:
    response = client.get("/api/v1/me", headers=_auth("u2"))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_the_customer_form_stays_public(client) -> None:
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Kettle broke",
            "body": "It stopped heating after a week.",
            "customer_email": "jo@example.com",
        },
    )

    assert response.status_code == 201
