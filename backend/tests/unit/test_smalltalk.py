from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from cms.rag.nodes import smalltalk as smalltalk_module


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


async def test_smalltalk_node_returns_the_reply_as_draft(monkeypatch) -> None:
    seen_queries: list[str] = []

    async def fake_core(query: str, conversation: str = "") -> str:
        seen_queries.append(query)
        return "Hi! Send me the complaint you're working on."

    monkeypatch.setattr(smalltalk_module, "smalltalk_core", fake_core)

    update = await smalltalk_module.smalltalk({"query": "hey there"})

    assert update == {"draft": "Hi! Send me the complaint you're working on."}
    assert seen_queries == ["hey there"]


async def test_smalltalk_node_passes_the_session_memory(monkeypatch) -> None:
    """A recap ("what have we covered?") is answered from the conversation."""
    seen: list[str] = []

    async def fake_core(query: str, conversation: str = "") -> str:
        seen.append(conversation)
        return "We covered the X200."

    monkeypatch.setattr(smalltalk_module, "smalltalk_core", fake_core)

    await smalltalk_module.smalltalk(
        {
            "query": "what have we covered?",
            "history_summary": "## X200 vacuum — stopped charging",
            "chat_history": [HumanMessage("hi"), AIMessage("Hello!")],
        }
    )

    assert "<summary>\n## X200 vacuum — stopped charging\n</summary>" in seen[0]
    assert "Agent: hi" in seen[0]


async def test_the_prompt_carries_the_conversation_and_the_message(monkeypatch) -> None:
    prompts: list[str] = []

    def fake_model(prompt_value) -> _FakeMessage:
        prompts.append(prompt_value.to_string())
        return _FakeMessage("We covered the X200.")

    monkeypatch.setattr(
        smalltalk_module, "get_chat_model", lambda model: RunnableLambda(fake_model)
    )

    await smalltalk_module.smalltalk_core(
        "what have we covered?", "\n<conversation>\nAgent: X200 stopped charging\n</conversation>\n"
    )

    assert "<conversation>\nAgent: X200 stopped charging\n</conversation>" in prompts[0]
    assert "<message>\nwhat have we covered?\n</message>" in prompts[0]
