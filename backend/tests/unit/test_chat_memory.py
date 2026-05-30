"""`new_turn` and the checkpointer: state must not leak from one turn into the next."""

from langchain_core.documents import Document
from langgraph.checkpoint.memory import InMemorySaver

from cms.rag import graph as graph_module
from cms.rag.state import new_turn

POLICY_HIT = (Document(page_content="policy clause"), 0.9)


def _install_nodes(monkeypatch, seen: list[dict]) -> None:
    """Stub every node, recording what `generate` was handed on each turn.

    The guard is scripted to fail, so turn 1 ends at `add_caveat` leaving
    `grounded=False` and `regenerated=True` behind — the exact state that would
    poison turn 2 without a reset.
    """

    async def input_guard(state):
        return {"query": state["query"], "input_blocked": False}

    async def analyze_query(state):
        return {"intent": "complaint_query", "policy_queries": [state["query"]]}

    async def retrieve_policies(state):
        return {"policy_hits": [POLICY_HIT], "no_match": False}

    async def retrieve_cases(state):
        return {"case_hits": []}

    async def generate(state):
        seen.append(
            {
                "grounded": state.get("grounded"),
                "regenerated": state.get("regenerated"),
                "draft": state.get("draft"),
                "guard_reasons": state.get("guard_reasons"),
                "citations": state.get("citations"),
            }
        )
        update = {"draft": f"draft for {state['query']}", "citations": []}
        # Mirrors the real node: this is what caps the retry at one.
        if state.get("grounded") is False:
            update["regenerated"] = True
        return update

    async def output_guard(state):
        return {"grounded": False, "guard_reasons": ["uncited claim"]}

    async def add_caveat(state):
        return {"draft": f"caveat + {state.get('draft', '')}"}

    for name, fn in [
        ("input_guard", input_guard),
        ("analyze_query", analyze_query),
        ("retrieve_policies", retrieve_policies),
        ("retrieve_cases", retrieve_cases),
        ("generate", generate),
        ("output_guard", output_guard),
        ("add_caveat", add_caveat),
    ]:
        monkeypatch.setattr(graph_module, name, fn)


async def test_a_second_turn_does_not_inherit_the_first_turns_state(monkeypatch) -> None:
    """The regression test for cross-turn leakage.

    Without `new_turn`, turn 2's first `generate` sees `grounded=False` and treats
    a fresh question as a retry — feeding turn 1's answer into the prompt as
    `<previous_draft>`, and permanently disabling the retry path via
    `regenerated`.
    """
    seen: list[dict] = []
    _install_nodes(monkeypatch, seen)
    graph = graph_module.build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "t-1", "user_id": "anonymous"}}

    await graph.ainvoke(new_turn("first question", "t-1", "anonymous"), config=config)
    await graph.ainvoke(new_turn("second question", "t-1", "anonymous"), config=config)

    # Turn 1 drafts twice (guard fails, one retry), so turn 2's first draft is #3.
    second_turn_first_draft = seen[2]
    assert second_turn_first_draft["grounded"] is None
    assert second_turn_first_draft["regenerated"] is False
    assert second_turn_first_draft["draft"] == ""
    assert second_turn_first_draft["guard_reasons"] == []
    assert second_turn_first_draft["citations"] == []


async def test_chat_history_accumulates_across_turns(monkeypatch) -> None:
    """Two turns leave four messages, alternating roles, oldest first."""
    _install_nodes(monkeypatch, [])
    graph = graph_module.build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "t-2", "user_id": "anonymous"}}

    await graph.ainvoke(new_turn("first question", "t-2", "anonymous"), config=config)
    await graph.ainvoke(new_turn("second question", "t-2", "anonymous"), config=config)

    history = (await graph.aget_state(config)).values["chat_history"]
    assert [message.type for message in history] == ["human", "ai", "human", "ai"]
    assert history[0].content == "first question"
    assert history[1].content.startswith("caveat +")


async def test_retrieved_chunks_are_not_carried_into_the_checkpoint(monkeypatch) -> None:
    """`record_turn` clears the hits, so a stored turn is not ~20 Documents wide."""
    _install_nodes(monkeypatch, [])
    graph = graph_module.build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "t-3", "user_id": "anonymous"}}

    await graph.ainvoke(new_turn("a question", "t-3", "anonymous"), config=config)

    values = (await graph.aget_state(config)).values
    assert values["policy_hits"] == []
    assert values["case_hits"] == []


# --- new_turn, the reset itself ---


def test_every_carried_over_slot_is_cleared() -> None:
    """Each of these is read before it is written on some path, so a stale value
    changes what the next turn does."""
    state = new_turn("a question", "s-1", "u-1")
    assert state["grounded"] is None
    assert state["regenerated"] is False
    assert state["draft"] == ""
    assert state["citations"] == []
    assert state["guard_reasons"] == []
    assert state["message_id"] == ""


def test_retrieval_slots_are_cleared_too() -> None:
    """Not a correctness bug today, but it keeps a smalltalk turn from
    checkpointing the previous complaint's retrieved chunks."""
    state = new_turn("a question", "s-1", "u-1")
    assert state["policy_hits"] == []
    assert state["case_hits"] == []
    assert state["no_match"] is False
    assert state["input_blocked"] is False


def test_the_turn_carries_its_identity() -> None:
    state = new_turn("a question", "s-1", "u-1")
    assert state["query"] == "a question"
    assert state["session_id"] == "s-1"
    assert state["user_id"] == "u-1"


def test_history_and_intent_are_left_alone() -> None:
    """`chat_history` is owned by `record_turn` — resetting it here would wipe the
    conversation. `intent` is a Literal that `analyze_query` always writes first,
    so None would be a type lie."""
    state = new_turn("a question", "s-1", "u-1")
    assert "chat_history" not in state
    assert "intent" not in state
