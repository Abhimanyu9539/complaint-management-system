"""Runtime access to Qdrant: the client, the sparse embedder, and the stores.

This module is about *reaching* the collections. Their shape — vector names,
payload fields, and the code that creates them — lives in
`create_qdrant_collections.py`, and the names below are imported from there so
reads and writes can never drift from what was created.

Every payload filter must use the dotted path `metadata.department`, never
`department`: LangChain nests all metadata under a `metadata` key. See
`create_qdrant_collections.py` for the full explanation.

BM25 IDF is computed per collection, so the sparse half of a hybrid score is
calibrated against whichever corpus it came from. Scores from the `cases` and
`policies` collections are therefore not comparable — merge results with RRF,
or take a fixed top-k from each, rather than sorting a combined list by raw
score. Reranked results are the exception: a cross-encoder scores the query and
chunk together, so `cms.retrieval.rerank` scores *are* comparable across
collections.
"""

import logging
from functools import lru_cache

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from cms.config.settings import get_settings
from cms.llm.embeddings.openai_embeddings import get_dense_embeddings
from cms.retrieval.vector_store.create_qdrant_collections import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)

logger = logging.getLogger(__name__)

# BM25 sparse embeddings, computed locally by fastembed — no API cost.
# Requires the collection's sparse vector to use the IDF modifier so Qdrant
# supplies the corpus statistics BM25 scoring needs (see create_qdrant_collections.py).
SPARSE_MODEL_NAME = "Qdrant/bm25"

# The client default (5s) is too tight for a hosted Qdrant: a cold hybrid query
# — dense + sparse prefetch plus server-side RRF — regularly exceeds it and
# surfaces as a bare ReadTimeout that looks like an outage rather than a knob.
QDRANT_TIMEOUT_SECONDS = 30


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """Sync Qdrant client, for `QdrantVectorStore` only.

    `QdrantVectorStore` accepts no async client and implements no async methods,
    so the store must be built on this one. Everything that talks to Qdrant
    *directly* — the collection entrypoint, and the ingestion pipeline's scroll
    and delete — uses `get_async_qdrant_client` instead.
    """
    settings = get_settings()
    try:
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=QDRANT_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Failed to construct Qdrant client for %s", settings.qdrant_url)
        raise
    logger.debug("Qdrant client constructed for %s", settings.qdrant_url)
    return client


@lru_cache
def get_async_qdrant_client() -> AsyncQdrantClient:
    """Async Qdrant client, for direct point and collection operations.

    Same url/key/timeout as the sync client above. Like the Supabase client this
    binds to the event loop that first uses it, so one loop per process.
    """
    settings = get_settings()
    try:
        client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=QDRANT_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception(
            "Failed to construct async Qdrant client for %s", settings.qdrant_url
        )
        raise
    logger.debug("Async Qdrant client constructed for %s", settings.qdrant_url)
    return client


@lru_cache
def get_sparse_embeddings() -> FastEmbedSparse:
    """Local BM25 sparse embeddings.

    The first call downloads and caches the ONNX model (~50 MB); later calls are
    instant. Cached here so that download happens at most once per process.
    """
    try:
        embeddings = FastEmbedSparse(model_name=SPARSE_MODEL_NAME)
    except Exception:
        logger.exception(
            "Failed to load sparse embedding model %s "
            "(first run downloads it — check network access)",
            SPARSE_MODEL_NAME,
        )
        raise
    logger.debug("Sparse embeddings ready: %s", SPARSE_MODEL_NAME)
    return embeddings


async def collection_stats(name: str) -> dict:
    """Point and vector counts for one collection.

    Uniquely in this module, this never raises. The admin dashboard has to be
    able to render its Supabase half when the vector store is unavailable —
    a degraded row is a strictly better answer than a blank page, and it is
    also the answer the operator actually needs in that moment.

    Two failures are distinguished, because their remedies are completely
    different and reporting both as "unreachable" sends someone to debug their
    network when the real fix is one command:

    - the collection does not exist yet  -> run `uv run cms-create-collections`
    - Qdrant itself cannot be reached    -> check QDRANT_URL and /health/deps

    `points_count` and `indexed_vectors_count` are Optional in the Qdrant API
    (they are approximate, and absent on some backends), so both are coerced to
    0 rather than propagating None into arithmetic.
    """
    missing = {
        "name": name,
        "reachable": True,
        "status": "missing",
        "points_count": 0,
        "indexed_vectors_count": 0,
        "segments_count": 0,
    }

    try:
        info = await get_async_qdrant_client().get_collection(name)
    except UnexpectedResponse as exc:
        # The server answered, so it is up — it just has no such collection.
        if exc.status_code == 404:
            logger.warning(
                "Qdrant collection '%s' does not exist — run `uv run cms-create-collections`",
                name,
            )
            return missing
        logger.exception("Qdrant rejected the request for collection '%s'", name)
        return {**missing, "reachable": False, "status": "unknown"}
    except ValueError as exc:
        # qdrant-client raises a bare ValueError for a missing collection on
        # some transports rather than surfacing the 404.
        if "not found" in str(exc).lower() or "doesn't exist" in str(exc).lower():
            logger.warning(
                "Qdrant collection '%s' does not exist — run `uv run cms-create-collections`",
                name,
            )
            return missing
        logger.exception("Could not read Qdrant collection '%s'", name)
        return {**missing, "reachable": False, "status": "unknown"}
    except Exception:
        logger.exception("Could not reach Qdrant for collection '%s'", name)
        return {**missing, "reachable": False, "status": "unknown"}

    return {
        "name": name,
        "reachable": True,
        # `status` is an enum on some client versions and a plain string on
        # others; normalising here keeps the response model simple.
        "status": str(getattr(info.status, "value", info.status)),
        "points_count": info.points_count or 0,
        "indexed_vectors_count": info.indexed_vectors_count or 0,
        "segments_count": info.segments_count or 0,
    }


@lru_cache
def get_vector_store(
    collection_name: str, mode: RetrievalMode = RetrievalMode.HYBRID
) -> QdrantVectorStore:
    """The vector store for one collection, opened in one retrieval mode.

    Takes the collection name explicitly — there are two collections (cases,
    policies) and no single default. `@lru_cache` now keys on
    `(collection_name, mode)`, so each combination gets its own store, e.g. a
    HYBRID store for writes and separate DENSE/SPARSE stores for retriever
    legs that want to run one side in isolation.

    `validate_collection_config` is deliberately left on: it turns this
    constructor into a cross-check that the collection was built with the vector
    names and dimensions `create_qdrant_collections.py` declares, failing loudly
    here instead of silently writing mismatched vectors. What that costs depends
    on the mode:

    - DENSE / HYBRID: one throwaway embeddings API call to learn the dense
      dimension — cheap, and why this is cached per collection per process
      rather than per call.
    - SPARSE: no API call at all — only the sparse vector name is checked.

    The default stays HYBRID so the ingestion write path (`ingestion.load.
    vector_loader`), which needs both vectors produced together, is unaffected
    by this parameter's addition.

    Requires the collection to exist — run scripts/create_qdrant_collection.py first.
    """
    try:
        store = QdrantVectorStore(
            client=get_qdrant_client(),
            collection_name=collection_name,
            embedding=get_dense_embeddings() if mode != RetrievalMode.SPARSE else None,
            sparse_embedding=get_sparse_embeddings() if mode != RetrievalMode.DENSE else None,
            retrieval_mode=mode,
            vector_name=DENSE_VECTOR_NAME,
            sparse_vector_name=SPARSE_VECTOR_NAME,
        )
    except Exception:
        logger.exception(
            "Failed to open vector store for collection '%s' in mode %s — "
            "run scripts/create_qdrant_collection.py if it does not exist yet",
            collection_name,
            mode,
        )
        raise
    logger.info("Vector store ready on collection '%s' (mode=%s)", collection_name, mode)
    return store
