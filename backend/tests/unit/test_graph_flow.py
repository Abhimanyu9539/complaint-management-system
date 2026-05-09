from langchain_core.documents import Document

from cms.rag import graph as graph_module

POLICY_HIT = (Document(page_content="policy clause"), 0.9)
CASE_HIT = (Document(page_content="past case"), 0.8)


def _install_nodes(monkeypatch, no_match: bool) -> list[str]:
    """Stub the LLM and retrieval nodes, so `build_graph` wires the real edges with no network.

    `join_retrieval` stays real — it is part of the wiring under test.
    """
    ran: list[str] = []

    async def analyze_query(state):
        ran.append("analyze_query")
        return {"intent": "complaint_query", "policy_queries": [state["query"]]}

    async def retrieve_policies(state):
        ran.append("retrieve_policies")
        return {"policy_hits": [] if no_match else [POLICY_HIT], "no_match": no_match}

    async def retrieve_cases(state):
        ran.append("retrieve_cases")
        return {"case_hits": [CASE_HIT]}

    async def generate(state):
        ran.append("generate")
        # Both retrievals must have landed before generate runs.
        assert state["policy_hits"] == [POLICY_HIT]
        assert state["case_hits"] == [CASE_HIT]
        return {"draft": "generated draft", "citations": []}

    async def no_match_node(state):
        ran.append("no_match")
        return {"draft": "no match reply", "citations": []}

    monkeypatch.setattr(graph_module, "analyze_query", analyze_query)
    monkeypatch.setattr(graph_module, "retrieve_policies", retrieve_policies)
    monkeypatch.setattr(graph_module, "retrieve_cases", retrieve_cases)
    monkeypatch.setattr(graph_module, "generate", generate)
    monkeypatch.setattr(graph_module, "no_match", no_match_node)
    return ran


async def test_policy_match_generates_after_both_retrievals(monkeypatch) -> None:
    ran = _install_nodes(monkeypatch, no_match=False)

    state = await graph_module.build_graph().ainvoke({"query": "my vacuum stopped charging"})

    assert state["draft"] == "generated draft"
    assert ran.index("generate") > max(ran.index("retrieve_policies"), ran.index("retrieve_cases"))
    assert "no_match" not in ran


async def test_no_policy_match_skips_generate(monkeypatch) -> None:
    ran = _install_nodes(monkeypatch, no_match=True)

    # Without the join, generate would run beside no_match and both would write `draft`.
    state = await graph_module.build_graph().ainvoke({"query": "q"})

    assert state["draft"] == "no match reply"
    assert "generate" not in ran
