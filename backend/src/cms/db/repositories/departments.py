"""Reads of the `departments` table.

A small reference table seeded by migration 0003 with the twelve routing
targets. Read-only from the application's side — departments change through a
migration, not through the API, because the classifier and the retrieval filters
are both written against this exact set.
"""

import logging

from cms.db.session import get_supabase

logger = logging.getLogger(__name__)

TABLE = "departments"

DEPARTMENT_COLUMNS = "id,name"
DEPARTMENT_DESCRIPTION_COLUMNS = "id,name,description"


def list_departments() -> list[dict]:
    """Every department, id and display name, ordered by name.

    Used to turn the `department_id` slugs stored on cases into labels, so ids
    never reach the UI.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select(DEPARTMENT_COLUMNS)
            .order("name", desc=False)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s rows", TABLE)
        raise
    return response.data or []


def list_department_descriptions() -> list[dict]:
    """Every department with its classifier description, ordered by name.

    Migration 0003's own comment: `description` "is fed verbatim into the
    Phase 3 department-classifier prompt" — this is that read. Separate from
    `list_departments()` rather than widening its column set, since that
    function's callers only need id/name and this one exists solely for the
    `analyze_query` node's prompt-building step.
    """
    try:
        response = (
            get_supabase()
            .table(TABLE)
            .select(DEPARTMENT_DESCRIPTION_COLUMNS)
            .order("name", desc=False)
            .execute()
        )
    except Exception:
        logger.exception("Failed to list %s descriptions", TABLE)
        raise
    return response.data or []
