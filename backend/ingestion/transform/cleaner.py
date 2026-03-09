"""Normalization and dedup helpers, shared by both corpora.

Content hashing is the dedup primitive the whole pipeline is built on: it is
what lets an unchanged document short-circuit before a single embedding call is
made, and what makes a re-ingest land on the same Qdrant point ids instead of
duplicating them. PII scrubbing belongs here too when it arrives.
"""

import hashlib


def compute_content_hash(text: str) -> str:
    """Stable hash of a document's full text — the short-circuit key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
