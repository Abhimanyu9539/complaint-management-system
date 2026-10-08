"""Document metadata copied onto every point.

The keys must match the payload indexes in `create_qdrant_collections`.
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
