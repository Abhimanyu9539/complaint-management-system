from cms.rag.nodes import smalltalk as smalltalk_module


async def test_smalltalk_node_returns_the_reply_as_draft(monkeypatch) -> None:
    seen_queries: list[str] = []

    async def fake_core(query: str) -> str:
        seen_queries.append(query)
        return "Hi! Send me the complaint you're working on."

    monkeypatch.setattr(smalltalk_module, "smalltalk_core", fake_core)

    update = await smalltalk_module.smalltalk({"query": "hey there"})

    assert update == {"draft": "Hi! Send me the complaint you're working on."}
    assert seen_queries == ["hey there"]
