"""Shared route dependencies."""

import logging

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


def get_user_id() -> str:
    """The caller's id — a placeholder until auth lands.

    There is no JWT verification anywhere in this API yet, so every request is
    the same anonymous user. The value is recorded in checkpoint metadata so a
    conversation can be attributed later; it authorises nothing, and a chat
    session is reachable by anyone holding its id.

    TODO: verify the Supabase JWT (`settings.supabase_jwks_url`) and return the
    `sub` claim. Only this function body changes — every route that depends on
    it already takes the user id as an argument.
    """
    return get_settings().anonymous_user_id
