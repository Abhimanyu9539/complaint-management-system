"""Document-level metadata, copied onto every point of a document.

These are the payload fields retrieval filters and cites on, so they are built
in one place per corpus rather than inline in the pipeline — the keys here must
stay in step with the payload indexes declared in
`retrieval.vector_store.qdrant_store`.

Neither corpus writes `doc_type`: cases and policies live in separate
collections, so the collection itself is the type discriminator.
"""


def case_metadata(case: dict) -> dict:
    """Payload fields shared by every chunk of one case."""
    return {
        "doc_id": case["id"],
        "department": case["department_id"],
        "category": case["category"],
        "title": case["title"],
        "source": case["source"],
    }


def policy_metadata(policy: dict) -> dict:
    """Payload fields shared by every chunk of one policy.

    `lifecycle` takes the slot `category` occupies for cases: it is what lets
    retrieval restrict to published clauses inside Qdrant.
    """
    return {
        "doc_id": policy["id"],
        "department": policy["department_id"],
        "lifecycle": policy["lifecycle"],
        "title": policy["title"],
        "source": policy["source"],
    }
