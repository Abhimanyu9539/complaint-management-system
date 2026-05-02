from cms.config.settings import get_settings
from cms.rag.nodes.no_match import no_match


async def test_no_match_returns_the_configured_message_as_draft() -> None:
    update = await no_match({"query": "how do I file a patent in Estonia", "no_match": True})

    assert update == {"draft": get_settings().no_match_message, "citations": []}


async def test_the_message_states_no_policy_was_found() -> None:
    """The honesty rule is the point of this node — guard the wording's intent."""
    message = get_settings().no_match_message.lower()

    assert "couldn't find" in message or "could not find" in message
