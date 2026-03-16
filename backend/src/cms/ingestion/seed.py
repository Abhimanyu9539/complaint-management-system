"""Register the on-disk seed corpus in Postgres and run it through the pipeline.

Policy files also get uploaded to Supabase Storage (the private `policy-files`
bucket created by migration 0018) so `policies.storage_path` is populated and a
future citation card can link back to the source document. Cases have no file
on disk to upload — a case is a record of what happened, never something
someone drags in — so `cases.storage_path` does not exist and this module
never sets one. `source='seed'` still marks every row here as fixture data
rather than a user upload.

Storage is written before the Postgres row — the opposite order from
`pipeline.py`'s Postgres-before-Qdrant rule (see that module's docstring). The
two rules do not conflict: both mean "never let the source of truth reference
something that is not there yet," and the direction depends on whether the
*other* store is discoverable. Qdrant is enumerated by retrieval, so a ghost
point gets found and cited with nothing in Postgres to explain it — Postgres
must come first there. Nothing enumerates the Storage bucket, so an orphaned
object from a failed upsert is simply unreachable, and the next run's
deterministic `seed/{filename}` key overwrites it in place — whereas a
Postgres row pointing at an object that was never written would be a live 404
in a citation card. Storage first is the safer direction for the same reason.

Re-running must update the same 54 rows rather than duplicate them. Both `cases`
and `policies` have a `source_ref TEXT UNIQUE` column for exactly this: the case
id (`C-1001`) for cases, the source filename (`warranty-policy.md`) for
policies. Upserting on `source_ref` makes the whole run idempotent without
deriving synthetic ids — and the pipeline's own content-hash short-circuit means
a second run costs zero OpenAI calls. The Storage upload is *not* gated on that
hash: the hash covers the policy body only (frontmatter is split off first
below), so a `version:` bump changes the file without changing the hash, and
gating would mean a run right after applying migration 0018 skips uploading
every already-indexed policy instead of backfilling them.

This module is the corpus-level runner; `pipeline.py` handles one document.
`cms/cli/seed.py` is the CLI wrapper around `run_seed`.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from cms.config.settings import get_settings
from cms.db.repositories.cases import upsert_case
from cms.db.repositories.policies import upsert_policy
from cms.ingestion.extract.cases_extractor import build_case_text, load_seed_cases
from cms.ingestion.extract.policy_extractor import find_seed_policies, read_policy_file
from cms.ingestion.load.storage_loader import upload_policy_file
from cms.ingestion.pipeline import IngestResult, ingest_case, ingest_policy

logger = logging.getLogger(__name__)


def resolve_seed_dir() -> Path:
    """Locate the seed corpus directory.

    The corpus is *not* package data — `backend/data/` is git-ignored, so it is
    neither committed nor built into the wheel, and the package is importable
    from anywhere now that it is installed. So rather than deriving the path
    from `__file__` and hoping, try in order:

    1. `SEED_DATA_DIR` from settings — what a container sets after mounting the
       corpus somewhere of its own choosing.
    2. `./data/seed` under the cwd, which is what running from `backend/` gives
       you and preserves the previous behaviour exactly.
    3. The source-tree `backend/data/seed`, relative to this file. Resolves for
       an editable install regardless of cwd; will not resolve from a wheel in
       site-packages, where option 1 is the answer.

    Raises FileNotFoundError naming every location tried, because "seeded 0
    documents" is a far worse outcome than a loud failure.
    """
    candidates: list[Path] = []

    configured = get_settings().seed_data_dir
    if configured is not None:
        candidates.append(Path(configured).expanduser())

    try:
        candidates.append(Path.cwd() / "data" / "seed")
    except OSError:
        logger.exception("Could not read the working directory; skipping it")

    # src/cms/ingestion/seed.py -> backend/
    candidates.append(Path(__file__).resolve().parents[3] / "data" / "seed")

    for candidate in candidates:
        if candidate.is_dir():
            logger.info("Using seed corpus at %s", candidate)
            return candidate

    raise FileNotFoundError(
        "Seed corpus directory not found. Tried: "
        + ", ".join(str(c) for c in candidates)
        + ". Set SEED_DATA_DIR to point at it."
    )


@dataclass
class SeedSummary:
    """What one corpus run did, for the caller's summary line."""

    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    # Storage outcomes for policies, tracked separately from ingest status: a
    # document can be `indexed` in Qdrant while its file upload failed (or the
    # reverse, on a re-run where the hash short-circuit skips re-indexing but
    # the upload still runs unconditionally).
    stored: int = 0
    upload_failed: int = 0

    def record(self, status: str) -> None:
        setattr(self, status, getattr(self, status) + 1)


def seed_case(case: dict) -> IngestResult:
    """Register one seed case, then ingest it."""
    title = f"{case['id']} — {case['department']} / {case['category']}"

    document_id = upsert_case(
        {
            "source_ref": case["id"],
            "title": title,
            "department_id": case["department"],
            "category": case["category"],
            "resolution_path": case["resolution_path"],
            "complaint_text": case["complaint_text"],
            "dept_guidance": case.get("dept_guidance"),
            "resolution_text": case["resolution_text"],
            "source": "seed",
        }
    )
    return ingest_case(document_id, build_case_text(case))


def seed_policy(path: Path) -> tuple[IngestResult, str | None]:
    """Register one seed policy file, then ingest its body.

    A company-wide policy omits `department` from its frontmatter entirely,
    which lands as NULL in `department_id` — the schema's marker for "applies
    to every department". `or None` on the rest matters for the same reason: the
    frontmatter parser yields `""` for a key present but empty, and an empty
    string is a FK violation on `department_id` and a cast error on the
    `effective_date` DATE column, where NULL is simply "not recorded".

    Uploads the file to Storage before registering the row, and folds
    `storage_path` / `mime_type` into it only on success. A transient upload
    failure must not block the RAG ingest — the index is the critical path,
    the file link a convenience — but it also must not clobber a previously
    good `storage_path`: PostgREST's upsert treats an omitted key as "leave
    unchanged" and an explicit `None` as "set to NULL", so those two keys are
    added to the row only when the upload actually succeeds. Returns the
    storage path (or `None`) alongside the ingest result so `run_seed` can
    count upload outcomes separately from indexing outcomes.
    """
    meta, body = read_policy_file(path)

    row = {
        "source_ref": path.name,
        "title": meta.get("title", path.stem),
        "department_id": meta.get("department") or None,
        "version": meta.get("version") or None,
        "effective_date": meta.get("effective_date") or None,
        # Seeded policies are published outright — they are the shipped
        # baseline, not a draft awaiting review — otherwise retrieval
        # filtering on lifecycle would find nothing.
        "lifecycle": "published",
        "source": "seed",
    }

    storage_path: str | None = None
    try:
        storage_path, mime_type = upload_policy_file(path)
        row["storage_path"] = storage_path
        row["mime_type"] = mime_type
    except Exception:
        logger.exception(
            "Storage upload failed for policy %s — indexing without a file link",
            path.name,
        )

    document_id = upsert_policy(row)
    return ingest_policy(document_id, body), storage_path


def run_seed(one: bool = False) -> SeedSummary:
    """Ingest the corpus. `one` ingests a single case — the walking-skeleton gate.

    Raises if the corpus itself cannot be read; individual documents are
    isolated, so one malformed case does not cost us the other 24 ingests.
    """
    seed_dir = resolve_seed_dir()

    cases = load_seed_cases(seed_dir / "cases.json")
    policies = [] if one else find_seed_policies(seed_dir / "policies")

    if one:
        cases = cases[:1]
        logger.info("--one: ingesting a single case document")

    summary = SeedSummary()

    for case in cases:
        try:
            summary.record(seed_case(case).status)
        except Exception:
            logger.exception("Case %s failed to ingest", case.get("id"))
            summary.failed += 1

    for path in policies:
        try:
            result, storage_path = seed_policy(path)
            summary.record(result.status)
            if storage_path is not None:
                summary.stored += 1
            else:
                summary.upload_failed += 1
        except Exception:
            logger.exception("Policy %s failed to ingest", path.name)
            summary.failed += 1

    logger.info(
        "Seed complete — indexed=%d skipped=%d failed=%d stored=%d/%d upload_failed=%d",
        summary.indexed,
        summary.skipped,
        summary.failed,
        summary.stored,
        len(policies),
        summary.upload_failed,
    )
    return summary
