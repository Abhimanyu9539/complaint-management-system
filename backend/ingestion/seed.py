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
`scripts/seed_data.py` is the CLI wrapper around `run_seed`.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from db.repositories.cases import upsert_case
from db.repositories.policies import upsert_policy
from ingestion.extract.cases_extractor import build_case_text, load_seed_cases
from ingestion.extract.policy_extractor import find_seed_policies, read_policy_file
from ingestion.pipeline import IngestResult, ingest_case, ingest_policy

logger = logging.getLogger(__name__)

# backend/data/seed/ — this file is backend/ingestion/seed.py.
SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
CASES_FILE = SEED_DIR / "cases.json"
POLICIES_DIR = SEED_DIR / "policies"


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
    cases = load_seed_cases(CASES_FILE)
    policies = [] if one else find_seed_policies(POLICIES_DIR)

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
