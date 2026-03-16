from unittest.mock import Mock

import pytest

from cms.ingestion import pipeline


def test_unchanged_case_skips_all_writes(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        lambda _: {"status": "indexed", "content_hash": "same", "title": "Case"},
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "same")
    write_chunks = Mock()
    upsert_points = Mock()
    monkeypatch.setattr(pipeline, "write_chunks", write_chunks)
    monkeypatch.setattr(pipeline, "upsert_points", upsert_points)

    result = pipeline.ingest_case("case-id", "unchanged text")

    assert result.status == "skipped"
    write_chunks.assert_not_called()
    upsert_points.assert_not_called()


def test_case_pipeline_writes_postgres_before_qdrant(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        lambda _: {
            "status": "pending",
            "content_hash": None,
            "title": "Case",
            "id": "case-id",
            "department_id": "billing",
            "category": "duplicate_charge",
            "source": "seed",
        },
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "new")
    monkeypatch.setattr(pipeline, "start_job", lambda *_: "job-id")
    monkeypatch.setattr(
        pipeline, "mark_case_processing", lambda *_: events.append("processing")
    )
    monkeypatch.setattr(pipeline, "chunk_case", lambda _: ["chunk"])
    monkeypatch.setattr(
        pipeline,
        "write_chunks",
        lambda *_: events.append("postgres")
        or [
            {
                "id": "chunk-id",
                "chunk_index": 0,
                "content_hash": "chunk-hash",
                "text": "chunk",
            }
        ],
    )
    monkeypatch.setattr(pipeline, "existing_point_ids", lambda *_: {"old-point"})
    monkeypatch.setattr(
        pipeline,
        "upsert_points",
        lambda *_: events.append("qdrant") or ["point-id"],
    )
    monkeypatch.setattr(
        pipeline,
        "delete_stale_points",
        lambda *_: events.append("delete-stale"),
    )
    monkeypatch.setattr(
        pipeline, "mark_case_indexed", lambda *_: events.append("indexed")
    )
    monkeypatch.setattr(pipeline, "finish_job", lambda *_: events.append("finished"))

    result = pipeline.ingest_case("case-id", "new text")

    assert result.status == "indexed"
    assert events.index("postgres") < events.index("qdrant")
    assert events.index("qdrant") < events.index("delete-stale")
    assert events[-2:] == ["indexed", "finished"]


def test_case_pipeline_records_document_and_job_failure(monkeypatch) -> None:
    mark_failed = Mock()
    fail_job = Mock()
    monkeypatch.setattr(
        pipeline,
        "fetch_case",
        lambda _: {
            "status": "pending",
            "content_hash": None,
            "title": "Case",
            "id": "case-id",
            "department_id": "billing",
            "category": "duplicate_charge",
            "source": "seed",
        },
    )
    monkeypatch.setattr(pipeline, "compute_content_hash", lambda _: "new")
    monkeypatch.setattr(pipeline, "start_job", lambda *_: "job-id")
    monkeypatch.setattr(pipeline, "mark_case_processing", lambda *_: None)
    monkeypatch.setattr(pipeline, "chunk_case", lambda _: ["chunk"])
    monkeypatch.setattr(
        pipeline,
        "write_chunks",
        Mock(side_effect=RuntimeError("chunk write failed")),
    )
    monkeypatch.setattr(pipeline, "mark_case_failed", mark_failed)
    monkeypatch.setattr(pipeline, "fail_job", fail_job)

    with pytest.raises(RuntimeError, match="chunk write failed"):
        pipeline.ingest_case("case-id", "new text")

    mark_failed.assert_called_once()
    fail_job.assert_called_once()
    assert "chunk write failed" in mark_failed.call_args.args[1]
    assert "chunk write failed" in fail_job.call_args.args[1]
