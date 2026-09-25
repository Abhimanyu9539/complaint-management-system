from langchain_core.documents import Document

from cms.rag.nodes.lookup_join_retrieval import lookup_join_retrieval

HIT = (Document(page_content="chunk"), 0.9)


async def test_nothing_from_either_corpus_is_no_match() -> None:
    update = await lookup_join_retrieval({"query": "q", "policy_hits": [], "case_hits": []})

    assert update == {"no_match": True}


async def test_policies_alone_are_a_match() -> None:
    update = await lookup_join_retrieval({"query": "q", "policy_hits": [HIT], "case_hits": []})

    assert update == {"no_match": False}


async def test_cases_alone_are_a_match() -> None:
    update = await lookup_join_retrieval({"query": "q", "policy_hits": [], "case_hits": [HIT]})

    assert update == {"no_match": False}
