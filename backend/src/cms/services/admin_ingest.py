"""Service logic behind the admin ingestion trigger/retry routes.

The route layer must return before the embedding run finishes (admin-api.md
§4: an inline call would hold the request for the length of an embedding run
and time out at the proxy long before it finishes). Every path here queues a
job row, then hands the actual `ingest_case`/`ingest_policy` call to a
`BackgroundTasks` callback that FastAPI runs after the response is sent.

Those callbacks are `async def`, so FastAPI awaits them on the event loop
rather than dispatching them to the threadpool. Everything they reach is
either awaited I/O or thread-offloaded — see `ingestion/load/vector_loader.py`,
where the embed-and-upsert step is the one call long enough to matter.

Two distinct background paths exist, over two distinct identifiers:

- The **trigger** (`mode="document"`) names a file in the on-disk seed corpus
  by its `source_ref` (a policy filename or a case id) — it may or may not
  already have a Postgres row. `_run_seed_document` registers it (upsert on
  `source_ref`) and ingests the freshly-read body, exactly as `cms-seed` does.
- The **retry** route names an existing job's *row*, a real Postgres id.
  `_run_document` recovers that row's text via `cms.ingestion.reingest`
  (Storage first, seed file second for policies) and re-ingests it. This is
  the only path that can act on a document with no seed file at all — e.g. one
  a future ticket-minted-case feature would create.
"""

import logging
from uuid import uuid4

from fastapi import BackgroundTasks

from cms.db.repositories import ingestion_jobs
from cms.db.repositories.cases import fetch_case_for_reingest
from cms.db.repositories.policies import fetch_policy_for_reingest
from cms.ingestion import reingest
from cms.ingestion import seed as seed_module
from cms.ingestion.pipeline import ingest_case, ingest_policy
from cms.schemas.admin import TriggerIngestionRequest, TriggerIngestionResponse

logger = logging.getLogger(__name__)


class UnknownDocument(Exception):
    """`source_ref` names no file in the seed corpus. Maps to 422."""


BUSY = "Another ingestion job for this corpus is already running."

# One ingest run at a time per corpus: two concurrent runs would race on the
# same Qdrant points and chunk rows (both key on document id, not job id). A
# guard, not a queue — the admin panel is operated by one person, and a second
# click should fail loudly rather than queue silently behind the first and
# leave the operator staring at "queued" with no explanation.
#
# A plain set rather than a lock: these callbacks are coroutines on a single
# event loop, so the membership test and the `add` below cannot be interleaved
# — there is no `await` between them. A `threading.Lock` would guard against a
# concurrency that no longer exists here.
_running: set[str] = set()


async def _run_document(doc_type: str, document_id: str, job_id: str) -> None:
    if doc_type in _running:
        await ingestion_jobs.fail_job(job_id, BUSY)
        return
    _running.add(doc_type)
    try:
        text = await (
            reingest.case_text(document_id)
            if doc_type == "case"
            else reingest.policy_text(document_id)
        )
        ingest = ingest_case if doc_type == "case" else ingest_policy
        await ingest(document_id, text, job_id=job_id)
    except Exception as exc:
        logger.exception("Background ingest failed for %s %s", doc_type, document_id)
        await ingestion_jobs.fail_job(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _running.discard(doc_type)


async def _run_seed_document(doc_type: str, source_ref: str, job_id: str) -> None:
    """Register one seed-corpus file (by `source_ref`) and ingest it.

    The job row was queued with a placeholder document id — a real one does
    not exist until the register step's upsert runs — so `set_job_document`
    patches the row before any embedding work starts. That ordering matters:
    if the ingest then fails, the row still points at a real document and
    `retry_job` can act on it, rather than being stuck pointing at nothing.
    """
    if doc_type in _running:
        await ingestion_jobs.fail_job(job_id, BUSY)
        return
    _running.add(doc_type)
    try:
        if doc_type == "case":
            case = seed_module.find_seed_case(source_ref)
            document_id, text = await seed_module.register_seed_case(case)
            await ingestion_jobs.set_job_document(job_id, document_id)
            await ingest_case(document_id, text, job_id=job_id)
        else:
            path = seed_module.find_seed_policy(source_ref)
            document_id, body, _storage_path = await seed_module.register_seed_policy(path)
            await ingestion_jobs.set_job_document(job_id, document_id)
            await ingest_policy(document_id, body, job_id=job_id)
    except Exception as exc:
        logger.exception("Background seed ingest failed for %s %s", doc_type, source_ref)
        await ingestion_jobs.fail_job(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _running.discard(doc_type)


async def _run_corpus(doc_type: str, batch_job_id: str) -> None:
    """Re-seed a whole corpus, summarised onto one placeholder job row.

    Each document ingested along the way still gets its own normal job row —
    exactly what `cms-seed` produces today — because `run_seed_one_type` never
    passes a `job_id` down. `batch_job_id` exists only so the 202 response and
    the UI have a single row to point at and poll while that fans out.
    """
    if doc_type in _running:
        await ingestion_jobs.fail_job(batch_job_id, BUSY)
        return
    _running.add(doc_type)
    try:
        await ingestion_jobs.claim_job(batch_job_id)
        summary = await seed_module.run_seed_one_type(doc_type)
        total = summary.failed + summary.indexed + summary.skipped
        if summary.failed:
            await ingestion_jobs.fail_job(
                batch_job_id,
                f"{summary.failed} of {total} document(s) failed — see their own job rows.",
            )
        else:
            await ingestion_jobs.finish_job(batch_job_id, summary.indexed, summary.indexed)
    except Exception as exc:
        logger.exception("Corpus re-seed failed for doc_type=%s", doc_type)
        await ingestion_jobs.fail_job(batch_job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _running.discard(doc_type)


async def trigger_ingestion(
    payload: TriggerIngestionRequest, background_tasks: BackgroundTasks
) -> TriggerIngestionResponse:
    """Queue a job row synchronously, then hand the embedding work to a background task.

    Raises UnknownDocument (→ 422, mapped by the route) when `mode='document'`
    names a `source_ref` not present in the seed corpus — checked here, before
    anything is queued, so the client gets an immediate answer instead of a
    job that fails a moment later. A missing seed corpus directory raises
    `FileNotFoundError`, not `UnknownDocument` — that is a deployment problem
    ("the corpus isn't mounted"), not "this document doesn't exist", and the
    route maps it to a 503 with its own message rather than a 422 that would
    tell the operator every single file is unknown.
    """
    if payload.mode == "document":
        source_ref = payload.source_ref
        assert source_ref is not None  # enforced by the request schema's validator

        try:
            if payload.doc_type == "case":
                seed_module.find_seed_case(source_ref)
            else:
                seed_module.find_seed_policy(source_ref)
        except LookupError as exc:
            raise UnknownDocument(str(exc)) from None

        # The real document id does not exist yet — it is created by the
        # register step inside `_run_seed_document`, which patches this row
        # via `set_job_document` before ingesting. See that function's
        # docstring, and `ingestion_jobs.document_id`'s NOT NULL constraint.
        job_id = await ingestion_jobs.queue_job(payload.doc_type, str(uuid4()))
        background_tasks.add_task(_run_seed_document, payload.doc_type, source_ref, job_id)
        return TriggerIngestionResponse(
            job_id=job_id,
            accepted=True,
            message=f"Queued an ingest for {source_ref} from the seed corpus.",
        )

    # mode == "seed": one placeholder job row summarising the whole corpus run
    # — see `_run_corpus`. `document_id` is a fresh id that names no real row;
    # `ingestion_jobs.document_id` has no FK by design (that table's own
    # docstring — rows already outlive documents that get deleted), so a
    # summary row whose id never matched anything is an expected shape, not a
    # dangling reference.
    batch_job_id = await ingestion_jobs.queue_job(payload.doc_type, str(uuid4()))
    background_tasks.add_task(_run_corpus, payload.doc_type, batch_job_id)
    corpus_label = "cases" if payload.doc_type == "case" else "policies"
    return TriggerIngestionResponse(
        job_id=batch_job_id,
        accepted=True,
        message=f"Queued a full re-seed for {corpus_label}.",
    )


async def retry_job(job_id: str, background_tasks: BackgroundTasks) -> TriggerIngestionResponse:
    """Re-ingest the document a finished/failed job referenced.

    Raises LookupError (→ 404, mapped by the route) when the job id itself is
    unknown. Returns `accepted: false` — not a 500 — when the job's document
    has since been deleted: `ingestion_jobs.document_id` has no FK by design,
    so an orphaned reference is an expected outcome, not an exceptional one.
    """
    job = await ingestion_jobs.fetch_job(job_id)
    doc_type, document_id = job["doc_type"], job["document_id"]

    try:
        if doc_type == "case":
            await fetch_case_for_reingest(document_id)
        else:
            await fetch_policy_for_reingest(document_id)
    except LookupError:
        return TriggerIngestionResponse(
            job_id=job_id,
            accepted=False,
            message="The document this job referenced no longer exists.",
        )

    new_job_id = await ingestion_jobs.queue_job(doc_type, document_id)
    background_tasks.add_task(_run_document, doc_type, document_id, new_job_id)
    return TriggerIngestionResponse(
        job_id=new_job_id,
        accepted=True,
        message="Queued a retry for this document.",
    )


async def rerun_stuck_document(
    doc_type: str, document_id: str, background_tasks: BackgroundTasks
) -> TriggerIngestionResponse:
    """Re-run a document stuck at `processing` — the dashboard queue panel's action.

    Distinct from both other entry points here: unlike `trigger_ingestion`'s
    `mode="document"`, this acts on an existing Postgres row by id, not a
    seed-corpus `source_ref` — a stuck document is by definition already
    registered, and it may not even have a seed file (a future non-seed
    document type would still get stuck the same way). Unlike `retry_job`, it
    does not start from a job row — a document stuck at `processing` may have
    *no* finished/failed job at all if the crash that stranded it happened
    before one was ever written, so there is nothing to resolve one from.

    Raises UnknownDocument (→ 422) if the row has since been deleted.
    """
    try:
        if doc_type == "case":
            await fetch_case_for_reingest(document_id)
        else:
            await fetch_policy_for_reingest(document_id)
    except LookupError as exc:
        raise UnknownDocument(str(exc)) from None

    job_id = await ingestion_jobs.queue_job(doc_type, document_id)
    background_tasks.add_task(_run_document, doc_type, document_id, job_id)
    return TriggerIngestionResponse(
        job_id=job_id,
        accepted=True,
        message="Queued a re-run for this document.",
    )
