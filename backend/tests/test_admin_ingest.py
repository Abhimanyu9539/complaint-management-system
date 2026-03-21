from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks

from cms.schemas.admin import TriggerIngestionRequest
from cms.services import admin_ingest


def _tasks() -> BackgroundTasks:
    return BackgroundTasks()


def test_trigger_document_mode_unknown_source_ref_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(side_effect=LookupError("no such seed policy")),
    )
    payload = TriggerIngestionRequest(doc_type="policy", mode="document", source_ref="missing.md")

    with pytest.raises(admin_ingest.UnknownDocument):
        admin_ingest.trigger_ingestion(payload, _tasks())


def test_trigger_document_mode_missing_corpus_is_not_unknown_document(monkeypatch) -> None:
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
        admin_ingest.trigger_ingestion(payload, _tasks())


def test_trigger_document_mode_queues_and_schedules_a_seed_run(monkeypatch) -> None:
    monkeypatch.setattr(admin_ingest.seed_module, "find_seed_policy", Mock(return_value="ignored"))
    queue_job = Mock(return_value="job-1")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    payload = TriggerIngestionRequest(
        doc_type="policy", mode="document", source_ref="warranty-policy.md"
    )
    tasks = _tasks()
    response = admin_ingest.trigger_ingestion(payload, tasks)

    assert response.job_id == "job-1"
    assert response.accepted is True
    doc_type, document_id = queue_job.call_args.args
    assert doc_type == "policy"
    assert document_id  # a placeholder uuid, not tied to a real row yet
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_seed_document
    assert task.args == ("policy", "warranty-policy.md", "job-1")


def test_run_seed_document_patches_the_job_row_before_ingesting(monkeypatch) -> None:
    """The job row must be pointed at the real document id *before* the ingest
    runs — otherwise a run that fails after registering leaves the row
    pointing at a placeholder that `retry_job` can never resolve."""
    events: list[tuple] = []

    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(return_value="policies/warranty-policy.md"),
    )

    def fake_register_seed_policy(path):
        events.append(("register", path))
        return "real-uuid", "policy body", "seed/warranty-policy.md"

    monkeypatch.setattr(admin_ingest.seed_module, "register_seed_policy", fake_register_seed_policy)

    def fake_set_job_document(job_id, document_id):
        events.append(("set_job_document", job_id, document_id))

    monkeypatch.setattr(admin_ingest.ingestion_jobs, "set_job_document", fake_set_job_document)

    def fake_ingest_policy(document_id, body, *, job_id=None):
        events.append(("ingest", document_id, body, job_id))

    monkeypatch.setattr(admin_ingest, "ingest_policy", fake_ingest_policy)

    admin_ingest._run_seed_document("policy", "warranty-policy.md", "job-1")

    assert events == [
        ("register", "policies/warranty-policy.md"),
        ("set_job_document", "job-1", "real-uuid"),
        ("ingest", "real-uuid", "policy body", "job-1"),
    ]
    # The lock must be released even on the success path.
    assert admin_ingest._locks["policy"].acquire(blocking=False)
    admin_ingest._locks["policy"].release()


def test_run_seed_document_fails_the_job_when_the_corpus_lock_is_held(monkeypatch) -> None:
    lock = admin_ingest._locks["policy"]
    assert lock.acquire(blocking=False)
    try:
        register = Mock()
        monkeypatch.setattr(admin_ingest.seed_module, "register_seed_policy", register)
        fail_job = Mock()
        monkeypatch.setattr(admin_ingest.ingestion_jobs, "fail_job", fail_job)

        admin_ingest._run_seed_document("policy", "warranty-policy.md", "job-1")

        fail_job.assert_called_once()
        register.assert_not_called()
    finally:
        lock.release()


def test_run_seed_document_fails_the_job_and_releases_the_lock_on_error(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.seed_module,
        "find_seed_policy",
        Mock(side_effect=RuntimeError("disk error")),
    )
    fail_job = Mock()
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "fail_job", fail_job)

    admin_ingest._run_seed_document("policy", "warranty-policy.md", "job-1")

    fail_job.assert_called_once()
    assert admin_ingest._locks["policy"].acquire(blocking=False)
    admin_ingest._locks["policy"].release()


def test_trigger_seed_mode_queues_a_placeholder_batch_job(monkeypatch) -> None:
    queue_job = Mock(return_value="batch-job-1")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    payload = TriggerIngestionRequest(doc_type="policy", mode="seed")
    tasks = _tasks()
    response = admin_ingest.trigger_ingestion(payload, tasks)

    assert response.job_id == "batch-job-1"
    assert response.accepted is True
    doc_type, document_id = queue_job.call_args.args
    assert doc_type == "policy"
    assert document_id  # a fresh uuid string, not tied to a real policy
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_corpus
    assert task.args == ("policy", "batch-job-1")


def test_retry_unknown_job_raises_lookup_error(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs, "fetch_job", Mock(side_effect=LookupError("no such job"))
    )

    with pytest.raises(LookupError):
        admin_ingest.retry_job("missing-job", _tasks())


def test_retry_missing_document_returns_not_accepted(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs,
        "fetch_job",
        Mock(return_value={"doc_type": "case", "document_id": "gone"}),
    )
    monkeypatch.setattr(
        admin_ingest, "fetch_case_for_reingest", Mock(side_effect=LookupError("gone"))
    )
    queue_job = Mock()
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    response = admin_ingest.retry_job("old-job", _tasks())

    assert response.accepted is False
    assert response.job_id == "old-job"
    queue_job.assert_not_called()


def test_rerun_stuck_document_queues_a_fresh_job_without_a_prior_job_row(monkeypatch) -> None:
    """The dashboard's queue panel acts on a document id directly — a stuck
    document may have no finished/failed job row to retry at all."""
    monkeypatch.setattr(admin_ingest, "fetch_policy_for_reingest", Mock(return_value={}))
    queue_job = Mock(return_value="job-3")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    tasks = _tasks()
    response = admin_ingest.rerun_stuck_document("policy", "policy-1", tasks)

    assert response.accepted is True
    assert response.job_id == "job-3"
    queue_job.assert_called_once_with("policy", "policy-1")
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_document
    assert task.args == ("policy", "policy-1", "job-3")


def test_rerun_stuck_document_raises_unknown_document_when_deleted(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest, "fetch_case_for_reingest", Mock(side_effect=LookupError("gone"))
    )

    with pytest.raises(admin_ingest.UnknownDocument):
        admin_ingest.rerun_stuck_document("case", "case-1", _tasks())


def test_retry_queues_a_new_job_row(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_ingest.ingestion_jobs,
        "fetch_job",
        Mock(return_value={"doc_type": "policy", "document_id": "policy-1"}),
    )
    monkeypatch.setattr(admin_ingest, "fetch_policy_for_reingest", Mock(return_value={}))
    queue_job = Mock(return_value="job-2")
    monkeypatch.setattr(admin_ingest.ingestion_jobs, "queue_job", queue_job)

    tasks = _tasks()
    response = admin_ingest.retry_job("old-job", tasks)

    assert response.accepted is True
    assert response.job_id == "job-2"
    queue_job.assert_called_once_with("policy", "policy-1")
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func is admin_ingest._run_document
    assert task.args == ("policy", "policy-1", "job-2")
