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
score.
"""

import logging
from functools import lru_cache

from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

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
    """Sync Qdrant client.

    Sync rather than async because both callers are sync — the collection
    entrypoint and the ingestion pipeline — and `QdrantVectorStore` requires a
    sync client. The `/health/deps` endpoint keeps its own `AsyncQdrantClient`.
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


@lru_cache
def get_vector_store(collection_name: str) -> QdrantVectorStore:
    """The hybrid (dense + sparse) vector store for one collection.

    Takes the collection name explicitly — there are two collections (cases,
    policies) and no single default. `@lru_cache` still applies: it now caches
    one store per collection instead of one per process, since `collection_name`
    is hashable.

    `validate_collection_config` is deliberately left on: it turns this
    constructor into a cross-check that the collection was built with the vector
    names and dimensions `create_qdrant_collections.py` declares, failing loudly
    here instead of silently writing mismatched vectors. That costs one throwaway
    embeddings API call to learn the dense dimension, which is why this is
    cached — once per collection per process, not once per document.

    Requires the collection to exist — run scripts/create_qdrant_collection.py first.
    """
    try:
        store = QdrantVectorStore(
            client=get_qdrant_client(),
            collection_name=collection_name,
            embedding=get_dense_embeddings(),
            sparse_embedding=get_sparse_embeddings(),
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name=DENSE_VECTOR_NAME,
            sparse_vector_name=SPARSE_VECTOR_NAME,
        )
    except Exception:
        logger.exception(
            "Failed to open vector store for collection '%s' — "
            "run scripts/create_qdrant_collection.py if it does not exist yet",
            collection_name,
        )
        raise
    logger.info("Vector store ready on collection '%s'", collection_name)
    return store
