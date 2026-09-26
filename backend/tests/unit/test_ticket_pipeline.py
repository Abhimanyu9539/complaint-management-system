from cms.schemas.ticket_classification import (
    DepartmentCandidate,
    TicketClassification,
    TicketEntities,
)
from cms.services import ticket_pipeline

CLASSIFICATION = TicketClassification(
    candidates=[
        DepartmentCandidate(department="warranty", score=0.75),
        DepartmentCandidate(department="tech_support", score=0.25),
    ],
    category="faulty_product",
    suggested_severity="high",
    entities=TicketEntities(order_no="#4521", product="X200"),
    reason="A physical fault inside the warranty period.",
)


class _FakeGraph:
    def __init__(self, result: dict | Exception) -> None:
        self.result = result
        self.inputs: list[dict] = []

    async def ainvoke(self, state: dict) -> dict:
        self.inputs.append(state)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _install(monkeypatch, graph_result: dict | Exception):
    """Stub the ticket read, the graph, and both writes. Returns (graph, updates, events)."""
    graph = _FakeGraph(graph_result)
    updates: list[tuple[str, dict]] = []
    events: list[tuple[str, str, dict]] = []

    async def fetch_ticket(ticket_id):
        return {"id": ticket_id, "subject": "X200 won't charge", "body": "Order #4521, dead after 3 months."}

    async def update_ticket(ticket_id, patch):
        updates.append((ticket_id, patch))
        return {"id": ticket_id, **patch}

    async def append_event(ticket_id, event, payload=None, actor_id=None):
        events.append((ticket_id, event, payload))

    monkeypatch.setattr(ticket_pipeline.tickets, "fetch_ticket", fetch_ticket)
    monkeypatch.setattr(ticket_pipeline.tickets, "update_ticket", update_ticket)
    monkeypatch.setattr(ticket_pipeline.ticket_events, "append_event", append_event)
    monkeypatch.setattr(ticket_pipeline, "get_ticket_graph", lambda: graph)
    return graph, updates, events


async def test_classified_ticket_is_saved_with_a_classified_event(monkeypatch) -> None:
    graph, updates, events = _install(monkeypatch, {"classification": CLASSIFICATION})

    await ticket_pipeline.process_ticket("t1")

    assert graph.inputs == [
        {"ticket_id": "t1", "query": "X200 won't charge\n\nOrder #4521, dead after 3 months."}
    ]
    assert updates == [
        (
            "t1",
            {
                "predicted_dept": "warranty",
                "dept_confidence": 0.75,
                "category": "faulty_product",
                "entities": {"order_no": "#4521", "product": "X200"},
                "suggested_severity": "high",
                "dept_candidates": [
                    {"department": "warranty", "score": 0.75},
                    {"department": "tech_support", "score": 0.25},
                ],
            },
        )
    ]
    assert [(ticket_id, event) for ticket_id, event, _ in events] == [("t1", "classified")]
    assert events[0][2]["reason"] == "A physical fault inside the warranty period."


async def test_blocked_ticket_is_left_alone_with_a_failed_event(monkeypatch) -> None:
    _, updates, events = _install(
        monkeypatch, {"input_blocked": True, "guard_reasons": ["injection"]}
    )

    await ticket_pipeline.process_ticket("t1")

    assert updates == []
    assert events == [("t1", "failed", {"stage": "input_guard", "reasons": ["injection"]})]


async def test_graph_failure_is_recorded_and_not_raised(monkeypatch) -> None:
    _, updates, events = _install(monkeypatch, ConnectionError("getaddrinfo failed"))

    await ticket_pipeline.process_ticket("t1")

    assert updates == []
    assert events == [
        ("t1", "failed", {"stage": "ticket_graph", "error": "ConnectionError: getaddrinfo failed"})
    ]
