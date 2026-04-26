"""The OpenRouter rerank HTTP call, driven against a mock transport — no network."""

import json

import httpx
import pytest
from langchain_core.documents import Document

from cms.llm.rerank.openrouter_rerank import OpenRouterRerank

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "voyageai/rerank-2.5-lite"


def _install_transport(monkeypatch, handler) -> None:
    """Route every httpx client the compressor builds through `handler`.

    Patched on `httpx` rather than injected, because the compressor deliberately
    constructs its own client per request (see its `acompress_documents`).
    """
    real_async, real_sync = httpx.AsyncClient, httpx.Client
    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_async(transport=transport, **kwargs)
    )
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: real_sync(transport=transport, **kwargs)
    )


def _reranker(top_n: int | None = 2) -> OpenRouterRerank:
    return OpenRouterRerank(
        api_key="sk-or-test", model=MODEL, base_url=BASE_URL, top_n=top_n
    )


def _documents() -> list[Document]:
    return [
        Document("Warranty > 2.3 Defects", metadata={"doc_id": "p1", "chunk_index": 0}),
        Document("Returns > 1.1 Window", metadata={"doc_id": "p2", "chunk_index": 3}),
        Document("Shipping > 4.0 Delays", metadata={"doc_id": "p3", "chunk_index": 1}),
    ]


def _ok(payload: dict):
    return lambda request: httpx.Response(200, json=payload)


async def test_sends_the_documented_request_shape(monkeypatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    _install_transport(monkeypatch, handler)
    await _reranker().acompress_documents(_documents(), "warranty period")

    request = seen[0]
    assert str(request.url) == f"{BASE_URL}/rerank"
    assert request.headers["Authorization"] == "Bearer sk-or-test"
    body = json.loads(request.content)
    assert body == {
        "model": MODEL,
        "query": "warranty period",
        # The text only — never the Document objects or their metadata.
        "documents": [
            "Warranty > 2.3 Defects",
            "Returns > 1.1 Window",
            "Shipping > 4.0 Delays",
        ],
        # OpenRouter's spelling of what the Voyage SDK calls `top_k`.
        "top_n": 2,
    }


async def test_omits_top_n_when_unset(monkeypatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"results": []})

    _install_transport(monkeypatch, handler)
    await _reranker(top_n=None).acompress_documents(_documents(), "warranty")

    assert "top_n" not in json.loads(seen[0].content)


async def test_maps_results_back_by_index_and_carries_metadata(monkeypatch) -> None:
    _install_transport(
        monkeypatch,
        _ok(
            {
                "results": [
                    {"index": 2, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.42},
                ],
                "model": MODEL,
                "usage": {"total_tokens": 137},
            }
        ),
    )

    ranked = await _reranker().acompress_documents(_documents(), "delays")

    # API order is preserved, and each result is matched to its source by `index`.
    assert [document.page_content for document in ranked] == [
        "Shipping > 4.0 Delays",
        "Warranty > 2.3 Defects",
    ]
    assert [document.metadata["doc_id"] for document in ranked] == ["p3", "p1"]
    # Original metadata survives alongside the two fields VoyageAIRerank also writes.
    assert ranked[0].metadata["chunk_index"] == 1
    assert ranked[0].metadata["relevance_score"] == 0.91
    assert ranked[0].metadata["total_tokens"] == 137


async def test_does_not_mutate_the_source_documents(monkeypatch) -> None:
    _install_transport(
        monkeypatch, _ok({"results": [{"index": 0, "relevance_score": 0.5}]})
    )
    documents = _documents()

    await _reranker().acompress_documents(documents, "warranty")

    assert "relevance_score" not in documents[0].metadata


async def test_missing_usage_leaves_total_tokens_none(monkeypatch) -> None:
    # `usage` is reported for cost only; the rerank must not depend on it.
    _install_transport(
        monkeypatch, _ok({"results": [{"index": 1, "relevance_score": 0.7}]})
    )

    ranked = await _reranker().acompress_documents(_documents(), "returns")

    assert ranked[0].metadata["total_tokens"] is None


async def test_empty_pool_costs_no_request(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made for an empty pool")

    _install_transport(monkeypatch, handler)

    assert await _reranker().acompress_documents([], "warranty") == []


async def test_an_error_status_raises_rather_than_passing_through(monkeypatch) -> None:
    # Degrading to the input order would score as a working reranker in the evals.
    _install_transport(monkeypatch, lambda request: httpx.Response(401))

    with pytest.raises(httpx.HTTPStatusError):
        await _reranker().acompress_documents(_documents(), "warranty")


async def test_an_out_of_range_index_raises(monkeypatch) -> None:
    _install_transport(
        monkeypatch, _ok({"results": [{"index": 9, "relevance_score": 0.5}]})
    )

    with pytest.raises(ValueError, match="index 9"):
        await _reranker().acompress_documents(_documents(), "warranty")


def test_the_sync_path_works_too(monkeypatch) -> None:
    _install_transport(
        monkeypatch, _ok({"results": [{"index": 1, "relevance_score": 0.88}]})
    )

    ranked = _reranker().compress_documents(_documents(), "returns")

    assert [document.page_content for document in ranked] == ["Returns > 1.1 Window"]
    assert ranked[0].metadata["relevance_score"] == 0.88
