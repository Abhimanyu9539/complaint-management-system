from cms.config.settings import get_settings
from cms.rag.nodes.lookup_no_match import lookup_no_match


async def test_lookup_no_match_returns_the_lookup_message_as_draft() -> None:
    update = await lookup_no_match({"query": "patents in Estonia", "no_match": True})

    assert update == {"draft": get_settings().lookup_no_match_message, "citations": []}
