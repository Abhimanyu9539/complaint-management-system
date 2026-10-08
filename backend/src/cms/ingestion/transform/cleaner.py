"""Normalisation and hashing for both corpora.

`compute_content_hash` hashes one chunk's text and fixes its point id, so it is never versioned.
`compute_ingest_key` hashes a document plus its processing recipe, so a recipe change re-ingests.
"""

import hashlib


def compute_content_hash(text: str) -> str:
    """Content address for one chunk. Never version this — see the module docstring."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_ingest_key(text: str, recipe: str) -> str:
    """Cache key for the short-circuit: the source text *and* how we process it."""
    return hashlib.sha256(f"{recipe}\n{text}".encode()).hexdigest()
