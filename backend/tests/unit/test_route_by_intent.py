from cms.rag.graph import RETRIEVE_POLICIES, SMALLTALK, route_by_intent


def test_complaint_goes_to_retrieval() -> None:
    assert route_by_intent({"query": "q", "intent": "complaint_query"}) == RETRIEVE_POLICIES


def test_smalltalk_goes_to_smalltalk() -> None:
    assert route_by_intent({"query": "hi", "intent": "smalltalk_or_meta"}) == SMALLTALK


def test_missing_intent_falls_back_to_smalltalk() -> None:
    assert route_by_intent({"query": "hi"}) == SMALLTALK
