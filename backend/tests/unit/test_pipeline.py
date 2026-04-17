from unittest.mock import AsyncMock

import pytest

from cms.ingestion import pipeline


def _a(fn):
    """Adapt a sync stub to the coroutine function the pipeline now awaits."""

    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


async def test_unchanged_case_skips_all_writes(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        _a(lambda _: {"status": "indexed", "content_hash": "same", "title": "Case"}),
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "same")
    write_chunks = AsyncMock()
    upsert_points = AsyncMock()
    monkeypatch.setattr(pipeline, "write_chunks", write_chunks)
    monkeypatch.setattr(pipeline, "upsert_points", upsert_points)

    result = await pipeline.ingest_case("case-id", "unchanged text")

    assert result.status == "skipped"
    write_chunks.assert_not_called()
    upsert_points.assert_not_called()


async def test_case_pipeline_writes_postgres_before_qdrant(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        _a(lambda _: {
            "status": "pending",
            "content_hash": None,
            "title": "Case",
            "id": "case-id",
            "department_id": "billing",
            "category": "duplicate_charge",
            "source": "seed",
        }),
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "new")
    monkeypatch.setattr(pipeline, "start_job", _a(lambda *_: "job-id"))
    monkeypatch.setattr(
        pipeline, "mark_case_processing", _a(lambda *_: events.append("processing"))
    )
    monkeypatch.setattr(pipeline, "chunk_case", lambda _: ["chunk"])
    monkeypatch.setattr(
        pipeline,
        "write_chunks",
        _a(lambda *_: events.append("postgres")
        or [
            {
                "id": "chunk-id",
                "chunk_index": 0,
                "content_hash": "chunk-hash",
                "text": "chunk",
            }
        ]),
    )
    monkeypatch.setattr(pipeline, "existing_point_ids", _a(lambda *_: {"old-point"}))
    monkeypatch.setattr(
        pipeline,
        "upsert_points",
        _a(lambda *_: events.append("qdrant") or ["point-id"]),
    )
    monkeypatch.setattr(
        pipeline,
        "delete_stale_points",
        _a(lambda *_: events.append("delete-stale")),
    )
    monkeypatch.setattr(
        pipeline, "mark_case_indexed", _a(lambda *_: events.append("indexed"))
    )
    monkeypatch.setattr(pipeline, "finish_job", _a(lambda *_: events.append("finished")))

    result = await pipeline.ingest_case("case-id", "new text")

    assert result.status == "indexed"
    assert events.index("postgres") < events.index("qdrant")
    assert events.index("qdrant") < events.index("delete-stale")
    assert events[-2:] == ["indexed", "finished"]


async def test_case_pipeline_records_document_and_job_failure(monkeypatch) -> None:
    mark_failed = AsyncMock()
    fail_job = AsyncMock()
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        _a(lambda _: {
            "status": "pending",
            "content_hash": None,
            "title": "Case",
            "id": "case-id",
            "department_id": "billing",
            "category": "duplicate_charge",
            "source": "seed",
        }),
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "new")
    monkeypatch.setattr(pipeline, "start_job", _a(lambda *_: "job-id"))
    monkeypatch.setattr(pipeline, "mark_case_processing", _a(lambda *_: None))
    monkeypatch.setattr(pipeline, "chunk_case", lambda _: ["chunk"])
    monkeypatch.setattr(
        pipeline,
        "write_chunks",
        AsyncMock(side_effect=RuntimeError("chunk write failed")),
    )
    monkeypatch.setattr(pipeline, "mark_case_failed", mark_failed)
    monkeypatch.setattr(pipeline, "fail_job", fail_job)

    with pytest.raises(RuntimeError, match="chunk write failed"):
        await pipeline.ingest_case("case-id", "new text")

    mark_failed.assert_called_once()
    fail_job.assert_called_once()
    assert "chunk write failed" in mark_failed.call_args.args[1]
    assert "chunk write failed" in fail_job.call_args.args[1]


async def test_force_bypasses_the_short_circuit(monkeypatch) -> None:
    """An unchanged case still re-embeds when `force=True` — the admin checkbox."""
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        _a(lambda _: {
            "status": "indexed",
            "content_hash": "same",
            "title": "Case",
            "id": "case-id",
            "department_id": "billing",
            "category": "duplicate_charge",
            "source": "seed",
        }),
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "same")
    monkeypatch.setattr(pipeline, "start_job", _a(lambda *_: "job-id"))
    monkeypatch.setattr(pipeline, "mark_case_processing", _a(lambda *_: None))
    monkeypatch.setattr(pipeline, "chunk_case", lambda _: ["chunk"])
    write_chunks = AsyncMock(
        return_value=[
            {"id": "chunk-id", "chunk_index": 0, "content_hash": "chunk-hash", "text": "chunk"}
        ]
    )
    monkeypatch.setattr(pipeline, "write_chunks", write_chunks)
    monkeypatch.setattr(pipeline, "existing_point_ids", _a(lambda *_: set()))
    upsert_points = AsyncMock(return_value=["point-id"])
    monkeypatch.setattr(pipeline, "upsert_points", upsert_points)
    monkeypatch.setattr(pipeline, "delete_stale_points", _a(lambda *_: None))
    monkeypatch.setattr(pipeline, "mark_case_indexed", _a(lambda *_: None))
    monkeypatch.setattr(pipeline, "finish_job", _a(lambda *_: None))

    result = await pipeline.ingest_case("case-id", "unchanged text", force=True)

    assert result.status == "indexed"
    write_chunks.assert_called_once()
    upsert_points.assert_called_once()


async def test_job_id_is_claimed_instead_of_started(monkeypatch) -> None:
    """A pre-queued job row (the HTTP trigger path) is claimed, not duplicated."""
    events: list[str] = []
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        _a(lambda _: {
            "status": "pending",
            "content_hash": None,
            "title": "Case",
            "id": "case-id",
            "department_id": "billing",
            "category": "duplicate_charge",
            "source": "seed",
        }),
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "new")
    start_job = AsyncMock()
    monkeypatch.setattr(pipeline, "start_job", start_job)
    monkeypatch.setattr(pipeline, "claim_job", _a(lambda job_id: events.append(f"claimed:{job_id}")))
    monkeypatch.setattr(pipeline, "mark_case_processing", _a(lambda *_: None))
    monkeypatch.setattr(pipeline, "chunk_case", lambda _: ["chunk"])
    monkeypatch.setattr(
        pipeline,
        "write_chunks",
        _a(lambda *_: [
            {"id": "chunk-id", "chunk_index": 0, "content_hash": "chunk-hash", "text": "chunk"}
        ]),
    )
    monkeypatch.setattr(pipeline, "existing_point_ids", _a(lambda *_: set()))
    monkeypatch.setattr(pipeline, "upsert_points", _a(lambda *_: ["point-id"]))
    monkeypatch.setattr(pipeline, "delete_stale_points", _a(lambda *_: None))
    monkeypatch.setattr(pipeline, "mark_case_indexed", _a(lambda *_: None))
    finish_job = AsyncMock()
    monkeypatch.setattr(pipeline, "finish_job", finish_job)

    result = await pipeline.ingest_case("case-id", "new text", job_id="pre-queued-id")

    assert result.status == "indexed"
    start_job.assert_not_called()
    assert events == ["claimed:pre-queued-id"]
    finish_job.assert_called_once_with("pre-queued-id", 1, 1)
