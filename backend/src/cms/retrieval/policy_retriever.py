"""Dense retrieval over the policies collection.
"""

import logging

from langchain_core.documents import Document
from langchain_qdrant import RetrievalMode
from qdrant_client import models

from cms.config.settings import get_settings
from cms.retrieval.vector_store.qdrant_store import get_vector_store

logger = logging.getLogger(__name__)

DEFAULT_K = 4
PUBLISHED = "published"

# One shared filter
PUBLISHED_FILTER = models.Filter(
    must=[
        models.FieldCondition(
            key="metadata.lifecycle",
            match=models.MatchValue(value=PUBLISHED),
        )
    ]
)


def retrieve_policies(query: str, k: int = DEFAULT_K) -> list[tuple[Document, float]]:
    """Top-`k` published policy chunks for `query`, most similar first."""
    collection = get_settings().qdrant_policies_collection
    store = get_vector_store(collection, mode=RetrievalMode.DENSE)

    try:
        hits = store.similarity_search_with_score(query, k=k, filter=PUBLISHED_FILTER)
    except Exception:
        logger.exception(
            "Dense policy search failed on '%s' for query %r", collection, query
        )
        raise

    # An empty result is a plausible-looking answer, so say so out loud: it means
    # either nothing is indexed yet or no chunk is `published`.
    logger.info(
        "Retrieved %d policy chunk(s) from '%s' for query %r", len(hits), collection, query
    )
    return hits
