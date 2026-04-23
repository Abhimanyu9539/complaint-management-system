"""Normalization and dedup helpers, shared by both corpora.

Two hashes, deliberately separate, because they answer different questions:

`compute_content_hash` is a **content address** — it hashes one chunk's text and
nothing else, which is what makes a re-ingest land on the same Qdrant point ids
instead of duplicating them. It must never be versioned: folding config into it
would re-mint every point id for text nobody edited.

`compute_ingest_key` is a **cache key** — it hashes a document's text *and* the
recipe used to process it, which is what lets an unchanged document short-circuit
before a single embedding call is made. Changing chunk size or the embedding
model changes the key, so the corpus it affects re-ingests rather than silently
skipping.

PII scrubbing belongs here too when it arrives.
"""

import hashlib


def compute_content_hash(text: str) -> str:
    """Content address for one chunk. Never version this — see the module docstring."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_ingest_key(text: str, recipe: str) -> str:
    """Cache key for the short-circuit: the source text *and* how we process it."""
    return hashlib.sha256(f"{recipe}\n{text}".encode()).hexdigest()
