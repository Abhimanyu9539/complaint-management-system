from cms.config.settings import get_settings
from cms.rag.nodes.lookup_caveat import lookup_caveat


async def test_the_answer_is_kept_under_the_caveat_and_reasons() -> None:
    state = {
        "query": "refund cases",
        "draft": "- Duplicate refunded [9].",
        "guard_reasons": ["The draft cites [9], which is not among the numbered sources."],
    }

    update = await lookup_caveat(state)

    assert update["draft"] == (
        f"{get_settings().grounding_caveat}\n"
        "- The draft cites [9], which is not among the numbered sources.\n\n"
        "- Duplicate refunded [9]."
    )
