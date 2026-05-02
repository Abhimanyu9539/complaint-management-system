"""Empty-retrieval branch: say so plainly instead of generating from nothing.
"""

import logging

from langsmith import traceable

from cms.config.settings import get_settings
from cms.rag.state import GraphState

logger = logging.getLogger(__name__)


@traceable(name="no_match")
async def no_match(state: GraphState) -> dict:
    """The graph node: a partial `GraphState` update.

    Writes `draft` — the same slot `smalltalk` fills — so everything downstream
    reads one field for "the reply", whichever branch produced it. `async` only
    to match the other nodes; there is nothing here to await.
    """
    logger.info("no_match: no policy chunks for %r", state["query"])
    return {"draft": get_settings().no_match_message, "citations": []}
