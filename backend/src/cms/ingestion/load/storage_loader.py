"""Upload seed policy files to Supabase Storage, so a citation can link to the source document."""

import asyncio
import logging
from pathlib import Path

from cms.config.settings import get_settings
from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

# Markdown is served as plain text, not `text/markdown`: no browser renders
# `text/markdown` inline, so clicking "Open document" would download the file
# instead of showing it. `storage_path` and `source_ref` still carry the `.md`
# extension, so the on-disk format stays evident even though the object is
# served as text/plain.
_CONTENT_TYPES: dict[str, str] = {
    ".md": "text/plain; charset=utf-8",
}
_DEFAULT_CONTENT_TYPE = "application/octet-stream"


async def upload_policy_file(path: Path) -> tuple[str, str]:
    """Upload one policy file to the policy bucket, upserting by key.

    Returns `(storage_path, mime_type)`: `storage_path` is the key the client
    reports it actually wrote, not a re-derived string, so it cannot disagree
    with what landed in the bucket; `mime_type` is the content-type set on
    that same object, returned so the caller persists the one value that is
    true for both instead of computing it twice and risking drift.

    Upserts unconditionally rather than gating on a content hash: `seed.py`
    calls this before the chunk-level content hash is known, and unconditional
    upload is what lets a re-run backfill objects for already-indexed policies
    (e.g. immediately after the bucket migration is first applied).
    """
    key = f"seed/{path.name}"
    content_type = _CONTENT_TYPES.get(path.suffix.lower(), _DEFAULT_CONTENT_TYPE)
    bucket = get_settings().supabase_policy_bucket

    try:
        response = await (
            get_supabase()
            .storage.from_(bucket)
            .upload(
                key,
                await asyncio.to_thread(path.read_bytes),
                {"content-type": content_type, "upsert": "true"},
            )
        )
    except Exception:
        logger.exception("Failed to upload %s to bucket '%s'", path.name, bucket)
        raise

    logger.debug("Uploaded %s to '%s' as %s", path.name, bucket, response.path)
    return response.path, content_type
