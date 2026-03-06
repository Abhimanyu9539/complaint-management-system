"""Register the seed corpus in Postgres and run it through the ingest pipeline.

The corpus lives on disk (data/seed/), so this script does not upload to
Supabase Storage — `documents.storage_path` stays NULL and `source='seed'`
marks these rows as fixture data rather than user uploads.

Document ids are derived, not random: `uuid5(SEED_NAMESPACE, "case:C-1001")`.
The schema has no natural unique key for a seed document, and without a stable
id every re-run would create a second copy of all 25 documents. Deriving the
primary key from the seed identity makes the whole script an upsert.

Usage (cwd must be backend/ — config.py loads a relative ".env"):

    uv run python scripts/seed.py --one     # one case, the walking-skeleton gate
    uv run python scripts/seed.py           # the full 25-document corpus
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

# Running a file inside scripts/ puts scripts/ on sys.path, not backend/, and the
# project is not pip-installed — so make `app` importable before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Importing from `app` first runs app/__init__.py, which injects the OS trust
# store into ssl. That must happen before any HTTPS client is constructed.
from app.ingestion.chunkers import build_case_text, parse_frontmatter  # noqa: E402
from app.ingestion.pipeline import IngestResult, ingest_document  # noqa: E402
from app.services.supabase_client import get_supabase  # noqa: E402

logger = logging.getLogger("seed")

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
CASES_FILE = SEED_DIR / "cases.json"
POLICIES_DIR = SEED_DIR / "policies"

# Fixed, like the point-id namespace: changing it would orphan every existing
# seed document instead of updating it.
SEED_NAMESPACE = uuid.UUID("c0ffee00-1111-4222-8333-444455556666")


def seed_document_id(key: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, key))


def upsert_document_row(row: dict) -> None:
    """Register (or refresh) the `documents` row before ingesting its text."""
    get_supabase().table("documents").upsert(row, on_conflict="id").execute()


def ingest_case(case: dict) -> IngestResult:
    document_id = seed_document_id(f"case:{case['id']}")
    title = f"{case['id']} — {case['department']} / {case['category']}"

    upsert_document_row(
        {
            "id": document_id,
            "title": title,
            "doc_type": "case",
            "department_id": case["department"],
            "category": case["category"],
            "source": "seed",
        }
    )
    return ingest_document(document_id, build_case_text(case))


def ingest_policy(path: Path) -> IngestResult:
    markdown = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(markdown)

    document_id = seed_document_id(f"policy:{path.name}")
    upsert_document_row(
        {
            "id": document_id,
            "title": meta.get("title", path.stem),
            "doc_type": "policy",
            "department_id": meta.get("department"),
            "category": None,
            "source": "seed",
        }
    )
    return ingest_document(document_id, body)


def run(one: bool) -> int:
    """Ingest the corpus. Returns a process exit code."""
    try:
        cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Could not read seed cases from %s", CASES_FILE)
        return 1

    policies = [] if one else sorted(POLICIES_DIR.glob("*.md"))
    if one:
        cases = cases[:1]
        logger.info("--one: ingesting a single case document")

    counts = {"indexed": 0, "skipped": 0, "failed": 0}

    # Each document is isolated: one malformed case should not cost us the
    # other 24 successful ingests.
    for case in cases:
        try:
            counts[ingest_case(case).status] += 1
        except Exception:
            logger.exception("Case %s failed to ingest", case.get("id"))
            counts["failed"] += 1

    for path in policies:
        try:
            counts[ingest_policy(path).status] += 1
        except Exception:
            logger.exception("Policy %s failed to ingest", path.name)
            counts["failed"] += 1

    logger.info(
        "Seed complete — indexed=%d skipped=%d failed=%d",
        counts["indexed"],
        counts["skipped"],
        counts["failed"],
    )
    return 1 if counts["failed"] else 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Ingest the synthetic seed corpus.")
    parser.add_argument(
        "--one",
        action="store_true",
        help="Ingest only the first case document (walking-skeleton check).",
    )
    args = parser.parse_args()

    try:
        return run(args.one)
    except Exception:
        logger.exception("Seed run failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
