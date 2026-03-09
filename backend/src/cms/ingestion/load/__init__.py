"""Load: write chunks to Postgres, then points to Qdrant.

Two loaders because there are two stores with different roles. Postgres is the
source of truth (`doc_store_loader`); Qdrant is a rebuildable index derived from
it (`vector_loader`). `pipeline.py` always calls them in that order — see its
module docstring for why the reverse is the dangerous direction.
"""
