"""Register the seed corpus in Postgres and run it through the ingest pipeline.

The corpus lives on disk (data/seed/), so this script does not upload to
Supabase Storage — `policies.storage_path` stays NULL and `source='seed'` marks
these rows as fixture data rather than user uploads.

Re-running this script must update the same 25 rows rather than duplicate them.
Both `cases` and `policies` have a `source_ref TEXT UNIQUE` column for exactly
this: the case id (`C-1001`) for cases, the source filename
(`warranty-policy.md`) for policies. Upserting on `source_ref` makes the whole
script idempotent without deriving synthetic ids.

Usage (cwd must be backend/ — config.py loads a relative ".env"):

    uv run python scripts/seed.py --one     # one case, the walking-skeleton gate
    uv run python scripts/seed.py           # the full 25-document corpus
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Running a file inside scripts/ puts scripts/ on sys.path, not backend/, and the
# project is not pip-installed — so make `app` importable before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Importing from `app` first runs app/__init__.py, which injects the OS trust
# store into ssl. That must happen before any HTTPS client is constructed.
from app.ingestion.chunkers import build_case_text, parse_frontmatter  # noqa: E402
from app.ingestion.pipeline import IngestResult, ingest_case, ingest_policy  # noqa: E402
from app.services.supabase_client import get_supabase  # noqa: E402

logger = logging.getLogger("seed")

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
CASES_FILE = SEED_DIR / "cases.json"
POLICIES_DIR = SEED_DIR / "policies"


def upsert_row(table: str, row: dict) -> str:
    """Upsert a row keyed by `source_ref`, returning its id."""
    response = get_supabase().table(table).upsert(row, on_conflict="source_ref").execute()
    return response.data[0]["id"]


def seed_case(case: dict) -> IngestResult:
    title = f"{case['id']} — {case['department']} / {case['category']}"

    document_id = upsert_row(
        "cases",
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
        },
    )
    return ingest_case(document_id, build_case_text(case))


def seed_policy(path: Path) -> IngestResult:
    markdown = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(markdown)

    # Seeded policies are published outright — they are the shipped baseline,
    # not a draft awaiting review — otherwise retrieval filtering on lifecycle
    # would find nothing.
    document_id = upsert_row(
        "policies",
        {
            "source_ref": path.name,
            "title": meta.get("title", path.stem),
            "department_id": meta.get("department"),
            "lifecycle": "published",
            "source": "seed",
        },
    )
    return ingest_policy(document_id, body)


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
            counts[seed_case(case).status] += 1
        except Exception:
            logger.exception("Case %s failed to ingest", case.get("id"))
            counts["failed"] += 1

    for path in policies:
        try:
            counts[seed_policy(path).status] += 1
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
