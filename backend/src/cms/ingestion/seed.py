"""Register the on-disk seed corpus in Postgres and run it through the pipeline.

The corpus lives on disk (data/seed/), so nothing here uploads to Supabase
Storage — `policies.storage_path` stays NULL and `source='seed'` marks these
rows as fixture data rather than user uploads.

Re-running must update the same 25 rows rather than duplicate them. Both `cases`
and `policies` have a `source_ref TEXT UNIQUE` column for exactly this: the case
id (`C-1001`) for cases, the source filename (`warranty-policy.md`) for
policies. Upserting on `source_ref` makes the whole run idempotent without
deriving synthetic ids — and the pipeline's own content-hash short-circuit means
a second run costs zero OpenAI calls.

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


def seed_policy(path: Path) -> IngestResult:
    """Register one seed policy file, then ingest its body."""
    meta, body = read_policy_file(path)

    # Seeded policies are published outright — they are the shipped baseline,
    # not a draft awaiting review — otherwise retrieval filtering on lifecycle
    # would find nothing.
    document_id = upsert_policy(
        {
            "source_ref": path.name,
            "title": meta.get("title", path.stem),
            "department_id": meta.get("department"),
            "lifecycle": "published",
            "source": "seed",
        }
    )
    return ingest_policy(document_id, body)


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
            summary.record(seed_policy(path).status)
        except Exception:
            logger.exception("Policy %s failed to ingest", path.name)
            summary.failed += 1

    logger.info(
        "Seed complete — indexed=%d skipped=%d failed=%d",
        summary.indexed,
        summary.skipped,
        summary.failed,
    )
    return summary
