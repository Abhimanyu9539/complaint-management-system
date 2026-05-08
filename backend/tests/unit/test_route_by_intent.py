from cms.rag.graph import route_after_retrieval, route_by_intent


def test_complaint_searches_policies_and_cases() -> None:
    assert route_by_intent({"query": "q", "intent": "complaint_query"}) == [
        "policy_search",
        "case_search",
    ]


def test_smalltalk_goes_to_smalltalk() -> None:
    assert route_by_intent({"query": "hi", "intent": "smalltalk_or_meta"}) == "other_query"


def test_missing_intent_falls_back_to_smalltalk() -> None:
    assert route_by_intent({"query": "hi"}) == "other_query"


def test_empty_retrieval_goes_to_no_match() -> None:
    assert route_after_retrieval({"query": "q", "no_match": True}) == "no_match_found"


def test_retrieved_chunks_go_to_generate() -> None:
    assert route_after_retrieval({"query": "q", "no_match": False}) == "match_found"


def test_missing_no_match_flag_goes_to_generate() -> None:
    assert route_after_retrieval({"query": "q"}) == "match_found"
