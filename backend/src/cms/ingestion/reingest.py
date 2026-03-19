"""Recover a document's raw text from an id alone, for the admin retry route.

`pipeline.ingest_case`/`ingest_policy` take `(id, raw_text)` because `seed.py`
already holds the text it just read off disk when it calls them. `retry_job`
(`services/admin_ingest.py`) only has a job's Postgres row id — this module is
the missing extraction step for that one path. The sibling trigger path
(`mode="document"`) never needs this: it names a seed-corpus file by
`source_ref` and reads it straight off disk via `seed.register_seed_*`.
`seed.py` never calls this module and never will: it always has the text for
free.
"""

import logging

from cms.config.settings import get_settings
from cms.db.repositories.cases import fetch_case_for_reingest
from cms.db.repositories.policies import fetch_policy_for_reingest
from cms.db.session import get_supabase
from cms.ingestion.extract.cases_extractor import build_case_text
from cms.ingestion.extract.policy_extractor import parse_frontmatter
from cms.ingestion.seed import resolve_seed_dir

logger = logging.getLogger(__name__)


class DocumentTextUnavailable(Exception):
    """A document's raw body cannot be recovered by any known route."""


def case_text(case_id: str) -> str:
    """Rebuild a case's embedded text from its own row.

    Cases are self-contained in Postgres (`complaint_text`, `dept_guidance`,
    `resolution_text`), so this is a straight read, not a search.
    """
    return build_case_text(fetch_case_for_reingest(case_id))


def policy_text(policy_id: str) -> str:
    """Recover a policy's body: Supabase Storage first, the seed file second.

    Policies have no body column (`db/repositories/policies.py`'s module
    docstring) — the text lives only in `policy_chunks` (already chunked, not
    what re-ingest needs) and in the source file. `storage_path` is populated
    for every seeded policy since migration 0018, so Storage is the primary
    route; the seed directory is the fallback for a policy seeded before that
    migration ran, or if the object was since deleted from the bucket.
    """
    row = fetch_policy_for_reingest(policy_id)

    storage_path = row.get("storage_path")
    if storage_path:
        try:
            raw = _download_from_storage(storage_path)
        except Exception:
            logger.exception(
                "Storage download failed for policy %s at %s; trying the seed file",
                policy_id,
                storage_path,
            )
        else:
            _, body = parse_frontmatter(raw)
            return body

    source_ref = row.get("source_ref")
    if source_ref:
        try:
            seed_path = resolve_seed_dir() / "policies" / source_ref
        except FileNotFoundError:
            seed_path = None
        if seed_path is not None and seed_path.is_file():
            _, body = parse_frontmatter(seed_path.read_text(encoding="utf-8"))
            return body

    raise DocumentTextUnavailable(
        f"Policy {policy_id} has no readable Storage object and no matching seed file."
    )


def _download_from_storage(storage_path: str) -> str:
    bucket = get_settings().supabase_policy_bucket
    data = get_supabase().storage.from_(bucket).download(storage_path)
    return data.decode("utf-8")
