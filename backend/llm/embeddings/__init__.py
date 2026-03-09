"""Embedding models.

Versioned separately from chat models: changing the model here changes the
vector space, which means every point in Qdrant has to be re-embedded before
retrieval means anything again.
"""
