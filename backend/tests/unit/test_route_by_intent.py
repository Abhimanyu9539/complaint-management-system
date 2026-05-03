from cms.rag.graph import (
    GENERATE,
    NO_MATCH,
    RETRIEVE_POLICIES,
    SMALLTALK,
    route_after_retrieval,
    route_by_intent,
)


def test_complaint_goes_to_retrieval() -> None:
    assert route_by_intent({"query": "q", "intent": "complaint_query"}) == RETRIEVE_POLICIES


def test_smalltalk_goes_to_smalltalk() -> None:
    assert route_by_intent({"query": "hi", "intent": "smalltalk_or_meta"}) == SMALLTALK


def test_missing_intent_falls_back_to_smalltalk() -> None:
    assert route_by_intent({"query": "hi"}) == SMALLTALK


def test_empty_retrieval_goes_to_no_match() -> None:
    assert route_after_retrieval({"query": "q", "no_match": True}) == NO_MATCH


def test_retrieved_chunks_go_to_generate() -> None:
    assert route_after_retrieval({"query": "q", "no_match": False}) == GENERATE


def test_missing_no_match_flag_goes_to_generate() -> None:
    assert route_after_retrieval({"query": "q"}) == GENERATE
