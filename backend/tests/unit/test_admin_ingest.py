from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks

from cms.schemas.admin import TriggerIngestionRequest
from cms.services import admin_ingest


def _tasks() -> BackgroundTasks:
    return BackgroundTasks()


async def test_trigger_document_mode_unknown_source_ref_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(side_effect=LookupError("no such seed policy")),
    )
    payload = TriggerIngestionRequest(doc_type="policy", mode="document", source_ref="missing.md")

    with pytest.raises(admin_ingest.UnknownDocument):
        await admin_ingest.trigger_ingestion(payload, _tasks())


async def test_trigger_document_mode_missing_corpus_is_not_unknown_document(monkeypatch) -> None:
    """A missing seed directory means 'the corpus isn't mounted', not '422 unknown document'."""
    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(side_effect=FileNotFoundError("seed corpus directory not found")),
    )
    payload = TriggerIngestionRequest(
        doc_type="policy", mode="document", source_ref="warranty-policy.md"
    )

    with pytest.raises(FileNotFoundError):
        await admin_ingest.trigger_ingestion(payload, _tasks())


async def test_trigger_document_mode_queues_and_schedules_a_seed_run(monkeypatch) -> None:
    monkeypatch.setattr(admin_ingest.seed_module, "find_seed_policy", Mock(return_value="ignored"))
    queue_job = AsyncMock(return_value="job-1")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    payload = TriggerIngestionRequest(
        doc_type="policy", mode="document", source_ref="warranty-policy.md"
    )
    tasks = _tasks()
    response = await admin_ingest.trigger_ingestion(payload, tasks)

    assert response.job_id == "job-1"
    assert response.accepted is True
    doc_type, document_id = queue_job.call_args.args
    assert doc_type == "policy"
    assert document_id  # a placeholder uuid, not tied to a real row yet
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_seed_document
    assert task.args == ("policy", "warranty-policy.md", "job-1", False)


async def test_run_seed_document_patches_the_job_row_before_ingesting(monkeypatch) -> None:
    """The job row must be pointed at the real document id *before* the ingest
    runs — otherwise a run that fails after registering leaves the row
    pointing at a placeholder that `retry_job` can never resolve."""
    events: list[tuple] = []

    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(return_value="policies/warranty-policy.md"),
    )

    async def fake_register_seed_policy(path):
        events.append(("register", path))
        return "real-uuid", "policy body", "seed/warranty-policy.md"

    monkeypatch.setattr(admin_ingest.seed_module, "register_seed_policy", fake_register_seed_policy)

    async def fake_set_job_document(job_id, document_id):
        events.append(("set_job_document", job_id, document_id))

    monkeypatch.setattr(admin_ingest.ingestion_jobs, "set_job_document", fake_set_job_document)

    async def fake_ingest_policy(document_id, body, *, force=False, job_id=None):
        events.append(("ingest", document_id, body, job_id))

    monkeypatch.setattr(admin_ingest, "ingest_policy", fake_ingest_policy)

    await admin_ingest._run_seed_document("policy", "warranty-policy.md", "job-1")

    assert events == [
        ("register", "policies/warranty-policy.md"),
        ("set_job_document", "job-1", "real-uuid"),
        ("ingest", "real-uuid", "policy body", "job-1"),
    ]
    # The corpus guard must be cleared even on the success path.
    assert "policy" not in admin_ingest._running


async def test_run_seed_document_fails_the_job_when_the_corpus_guard_is_held(monkeypatch) -> None:
    admin_ingest._running.add("policy")
    try:
        register = AsyncMock()
        monkeypatch.setattr(admin_ingest.seed_module, "register_seed_policy", register)
        fail_job = AsyncMock()
        monkeypatch.setattr(admin_ingest.ingestion_jobs, "fail_job", fail_job)

        await admin_ingest._run_seed_document("policy", "warranty-policy.md", "job-1")

        fail_job.assert_called_once()
        register.assert_not_called()
    finally:
        admin_ingest._running.discard("policy")


async def test_run_seed_document_fails_the_job_and_clears_the_guard_on_error(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(side_effect=RuntimeError("disk error")),
    )
    fail_job = AsyncMock()
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "fail_job", fail_job)

    await admin_ingest._run_seed_document("policy", "warranty-policy.md", "job-1")

    fail_job.assert_called_once()
    assert "policy" not in admin_ingest._running


async def test_trigger_seed_mode_queues_a_placeholder_batch_job(monkeypatch) -> None:
    queue_job = AsyncMock(return_value="batch-job-1")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    payload = TriggerIngestionRequest(doc_type="policy", mode="seed")
    tasks = _tasks()
    response = await admin_ingest.trigger_ingestion(payload, tasks)

    assert response.job_id == "batch-job-1"
    assert response.accepted is True
    doc_type, document_id = queue_job.call_args.args
    assert doc_type == "policy"
    assert document_id  # a fresh uuid string, not tied to a real policy
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_corpus
    assert task.args == ("policy", "batch-job-1", False)


async def test_trigger_seed_mode_passes_force_through_to_the_corpus_run(monkeypatch) -> None:
    """`force` was plumbed to `pipeline` but never set by any caller — the
    override for a strategy change the ingest-key recipe cannot catch."""
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs, "queue_job", AsyncMock(return_value="batch-job-2")
    )

    payload = TriggerIngestionRequest(doc_type="case", mode="seed", force=True)
    tasks = _tasks()
    await admin_ingest.trigger_ingestion(payload, tasks)

    assert tasks.tasks[0].args == ("case", "batch-job-2", True)


async def test_retry_unknown_job_raises_lookup_error(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs, "fetch_job", AsyncMock(side_effect=LookupError("no such job"))
    )

    with pytest.raises(LookupError):
        await admin_ingest.retry_job("missing-job", _tasks())


async def test_retry_missing_document_returns_not_accepted(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs,
        "fetch_job",
        AsyncMock(return_value={"doc_type": "case", "document_id": "gone"}),
    )
    monkeypatch.setattr(
        admin_ingest, "fetch_case_for_reingest", AsyncMock(side_effect=LookupError("gone"))
    )
    queue_job = AsyncMock()
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    response = await admin_ingest.retry_job("old-job", _tasks())

    assert response.accepted is False
    assert response.job_id == "old-job"
    queue_job.assert_not_called()


async def test_rerun_stuck_document_queues_a_fresh_job_without_a_prior_job_row(monkeypatch) -> None:
    """The dashboard's queue panel acts on a document id directly — a stuck
    document may have no finished/failed job row to retry at all."""
    monkeypatch.setattr(admin_ingest, "fetch_policy_for_reingest", AsyncMock(return_value={}))
    queue_job = AsyncMock(return_value="job-3")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    tasks = _tasks()
    response = await admin_ingest.rerun_stuck_document("policy", "policy-1", tasks)

    assert response.accepted is True
    assert response.job_id == "job-3"
    queue_job.assert_called_once_with("policy", "policy-1")
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_document
    assert task.args == ("policy", "policy-1", "job-3")


async def test_rerun_stuck_document_raises_unknown_document_when_deleted(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest, "fetch_case_for_reingest", AsyncMock(side_effect=LookupError("gone"))
    )

    with pytest.raises(admin_ingest.UnknownDocument):
        await admin_ingest.rerun_stuck_document("case", "case-1", _tasks())


async def test_retry_queues_a_new_job_row(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs,
        "fetch_job",
        AsyncMock(return_value={"doc_type": "policy", "document_id": "policy-1"}),
    )
    monkeypatch.setattr(admin_ingest, "fetch_policy_for_reingest", AsyncMock(return_value={}))
    queue_job = AsyncMock(return_value="job-2")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    tasks = _tasks()
    response = await admin_ingest.retry_job("old-job", tasks)

    assert response.accepted is True
    assert response.job_id == "job-2"
    queue_job.assert_called_once_with("policy", "policy-1")
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_document
    assert task.args == ("policy", "policy-1", "job-2")
