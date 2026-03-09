"""Offline write path: corpus text in, Postgres chunks + Qdrant points out.

Composed as Extract → Transform → Load, with `pipeline.py` wiring the three
together and owning the crash-safety protocol. Nothing here is imported by a
request handler — ingestion runs from `scripts/`, not from the API.
"""
