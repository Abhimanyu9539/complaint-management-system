from cms.rag.graph import route_after_input_guard, route_by_intent
from cms.rag.subgraphs.complaint import route_after_output_guard, route_after_retrieval
from cms.rag.subgraphs.lookup import (
    route_after_lookup_guard,
    route_after_lookup_retrieval,
)


def test_complaint_goes_to_the_complaint_lane() -> None:
    assert route_by_intent({"query": "q", "intent": "complaint_query"}) == "complaint"


def test_knowledge_lookup_goes_to_the_lookup_lane() -> None:
    assert route_by_intent({"query": "q", "intent": "knowledge_lookup"}) == "lookup"


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


def test_blocked_input_goes_to_blocked_input() -> None:
    assert route_after_input_guard({"query": "q", "input_blocked": True}) == "blocked"


def test_allowed_input_goes_to_analyze_query() -> None:
    assert route_after_input_guard({"query": "q", "input_blocked": False}) == "allowed"


def test_grounded_draft_ends_the_graph() -> None:
    assert route_after_output_guard({"query": "q", "grounded": True}) == "grounded"


def test_unchecked_draft_ends_the_graph() -> None:
    # Guardrails disabled: `grounded` is None.
    assert route_after_output_guard({"query": "q", "grounded": None}) == "grounded"


def test_first_ungrounded_draft_is_retried() -> None:
    assert route_after_output_guard({"query": "q", "grounded": False}) == "retry"


def test_ungrounded_draft_after_retry_gets_the_caveat() -> None:
    state = {"query": "q", "grounded": False, "regenerated": True}
    assert route_after_output_guard(state) == "still_ungrounded"


def test_empty_lookup_goes_to_lookup_no_match() -> None:
    assert route_after_lookup_retrieval({"query": "q", "no_match": True}) == "no_match_found"


def test_lookup_hits_go_to_lookup_generate() -> None:
    assert route_after_lookup_retrieval({"query": "q", "no_match": False}) == "match_found"


def test_missing_no_match_flag_goes_to_lookup_generate() -> None:
    assert route_after_lookup_retrieval({"query": "q"}) == "match_found"


def test_grounded_lookup_answer_ends_the_graph() -> None:
    assert route_after_lookup_guard({"query": "q", "grounded": True}) == "grounded"


def test_unchecked_lookup_answer_ends_the_graph() -> None:
    assert route_after_lookup_guard({"query": "q", "grounded": None}) == "grounded"


def test_ungrounded_lookup_answer_gets_the_caveat_without_a_retry() -> None:
    assert route_after_lookup_guard({"query": "q", "grounded": False}) == "ungrounded"
