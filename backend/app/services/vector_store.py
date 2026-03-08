"""The single definition of the two Qdrant collections' shape.

Cases and policies are separate corpora — separate Postgres tables, separate
write permissions, separate chunking — and that separation carries through to
retrieval as two Qdrant collections rather than one collection filtered by a
`doc_type` field. The collection itself is the discriminator, so `doc_type` is
not a payload field in either collection.

Everything that touches vectors — `scripts/create_qdrant_collection.py` (Step 3)
and the ingestion pipeline / retrieval nodes (Step 4+) — imports its vector
names and indexed fields from here, so the collections that get *created* and
the collections that get *written to* can never drift apart.

Payload layout
--------------
Writes and reads go through ``langchain_qdrant.QdrantVectorStore``, which
hardcodes its payload shape: chunk text under ``page_content``, all metadata
nested under a single ``metadata`` key. There is no flat-metadata option
(``metadata_payload_key`` renames the wrapper, it cannot remove it)::

    {
      "page_content": "<chunk text>",
      "metadata": {"doc_id": ..., "department": ..., ...}
    }

Consequence: every payload filter must use the dotted path
``metadata.department``, never ``department``. Qdrant indexes and filters
nested paths natively, so this costs nothing at retrieval time — but a filter
written against the flat name silently matches zero points.

BM25 IDF is computed per collection, so the sparse half of a hybrid score is
calibrated against whichever corpus it came from. Scores from the `cases` and
`policies` collections are therefore not comparable — merge results with RRF,
or take a fixed top-k from each, rather than sorting a combined list by raw
score.
"""

import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from app.config import get_settings

logger = logging.getLogger(__name__)

# Named vectors, per build.md §0.4. LangChain's defaults ("" and
# "langchain-sparse") are accepted as constructor args, so we keep the clearer
# names rather than inheriting them.
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# BM25 sparse embeddings, computed locally by fastembed — no API cost.
# Requires the collection's sparse vector to use the IDF modifier so Qdrant
# supplies the corpus statistics BM25 scoring needs.
SPARSE_MODEL_NAME = "Qdrant/bm25"

# The client default (5s) is too tight for a hosted Qdrant: a cold hybrid query
# — dense + sparse prefetch plus server-side RRF — regularly exceeds it and
# surfaces as a bare ReadTimeout that looks like an outage rather than a knob.
QDRANT_TIMEOUT_SECONDS = 30

# Fields retrieval filters on, as dotted paths into `metadata`. Split per
# collection: cases filter on `category`, policies filter on `lifecycle` (so
# retrieval can restrict to `published` clauses inside Qdrant).
CASE_PAYLOAD_FIELDS: tuple[str, ...] = (
    "metadata.doc_id",
    "metadata.department",
    "metadata.category",
)
POLICY_PAYLOAD_FIELDS: tuple[str, ...] = (
    "metadata.doc_id",
    "metadata.department",
    "metadata.lifecycle",
)


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """Sync Qdrant client.

    Sync rather than async because both callers are sync — the creation script
    and the ingestion pipeline — and `QdrantVectorStore` requires a sync client.
    The `/health/deps` endpoint keeps its own `AsyncQdrantClient`.
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
def get_dense_embeddings() -> OpenAIEmbeddings:
    """Dense embeddings via LangChain, so LangSmith traces the calls for free."""
    settings = get_settings()
    try:
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )
    except Exception:
        logger.exception(
            "Failed to construct dense embeddings (model=%s)", settings.embedding_model
        )
        raise
    logger.debug("Dense embeddings ready: %s", settings.embedding_model)
    return embeddings


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
    constructor into a cross-check that `scripts/create_qdrant_collection.py`
    built the collection with the vector names and dimensions we expect, failing
    loudly here instead of silently writing mismatched vectors. That validation
    costs one throwaway embeddings API call to learn the dense dimension, which
    is why this is cached — once per collection per process, not once per document.

    Requires the collection to exist — run the creation script first.
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
