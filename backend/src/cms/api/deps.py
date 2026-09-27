"""Shared route dependencies: who is calling, and whether they may.

A caller sends the Supabase access token as `Authorization: Bearer <jwt>`. It is
verified against the project's public signing keys (fetched once, then cached),
and the caller must have an active `profiles` row. The token itself is never logged.
"""

import asyncio
import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cms.config.settings import get_settings
from cms.db.repositories import profiles
from cms.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)

NOT_SIGNED_IN = "Sign in to continue."
NO_PROFILE = "Your account is not set up as an agent."
ADMINS_ONLY = "Only admins can do this."
AUTH_UNAVAILABLE = "Sign-in could not be checked right now. Try again in a moment."

_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwk_client() -> jwt.PyJWKClient:
    settings = get_settings()
    return jwt.PyJWKClient(
        settings.supabase_jwks_url,
        cache_keys=True,
        lifespan=settings.jwks_cache_seconds,
        timeout=settings.jwks_timeout_seconds,
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401, detail=NOT_SIGNED_IN, headers={"WWW-Authenticate": "Bearer"}
    )


async def _verify(token: str) -> dict:
    """The token's claims. 401 for any bad token, 503 when the signing keys can't be fetched."""
    settings = get_settings()
    try:
        # Blocks only when the key isn't cached yet, so the network read stays off the loop.
        signing_key = await asyncio.to_thread(_jwk_client().get_signing_key_from_jwt, token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=settings.supabase_jwt_algorithms,
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
            leeway=settings.supabase_jwt_leeway_seconds,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWKClientConnectionError:
        logger.exception("auth: could not fetch the signing keys from %s", settings.supabase_jwks_url)
        raise HTTPException(status_code=503, detail=AUTH_UNAVAILABLE) from None
    except jwt.PyJWTError as exc:
        logger.warning("auth: token rejected: %s", exc)
        raise _unauthorized() from None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """The signed-in agent. 401 without a valid token, 403 without an active profile."""
    if credentials is None:
        raise _unauthorized()

    claims = await _verify(credentials.credentials)
    user_id = claims["sub"]
    try:
        profile = await profiles.fetch_profile(user_id)
    except LookupError:
        logger.warning("auth: user %s has no profile", user_id)
        raise HTTPException(status_code=403, detail=NO_PROFILE) from None
    except Exception:
        logger.exception("auth: could not read the profile of user %s", user_id)
        raise HTTPException(status_code=503, detail=AUTH_UNAVAILABLE) from None

    if not profile.get("is_active"):
        logger.warning("auth: user %s is inactive", user_id)
        raise HTTPException(status_code=403, detail=NO_PROFILE)

    return CurrentUser(
        id=profile["id"],
        email=profile["email"],
        display_name=profile.get("display_name"),
        role=profile["role"],
    )


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """The signed-in user, if they are an admin. 403 otherwise."""
    if user.role != "admin":
        logger.warning("auth: user %s (%s) refused an admin route", user.id, user.role)
        raise HTTPException(status_code=403, detail=ADMINS_ONLY)
    return user
