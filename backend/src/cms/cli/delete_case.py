"""CLI entrypoint to remove a ticket's past case from the knowledge base.

    cms-delete-case T-14
    cms-delete-case 14

Only a flywheel case can be removed this way; seed cases come from the seed corpus.
"""

import argparse
import asyncio
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl before any HTTPS client is constructed.
from cms.config.logging_config import setup_logging
from cms.config.settings import get_settings
from cms.db.repositories import cases, ticket_events, tickets
from cms.ingestion.load.vector_loader import delete_stale_points, existing_point_ids

logger = logging.getLogger("cms.cli.delete_case")


def parse_ticket_no(value: str) -> int:
    """`T-14` or `14` -> 14."""
    return int(value.strip().upper().removeprefix("T-"))


async def delete_ticket_case(ticket_no: int) -> dict:
    """Remove the case minted from ticket `ticket_no`, and return it with its point count.

    Crash-safe order (migration 0005): flag the row `deleting`, remove the Qdrant
    points, then delete the row, whose chunk rows cascade. Raises `LookupError` for
    no ticket or no case, and `ValueError` for a seed case.
    """
    ticket = await tickets.fetch_ticket_by_no(ticket_no)
    case = await cases.fetch_case_by_ticket(ticket["id"])
    if case is None:
        raise LookupError(f"T-{ticket_no} has no case in the knowledge base.")
    if case["source"] != "flywheel":
        raise ValueError(f"{case['title']} is a seed case; it is not removed with this command.")

    collection = get_settings().qdrant_cases_collection
    await cases.mark_case_deleting(case["id"])
    point_ids = await existing_point_ids(collection, case["id"])
    await delete_stale_points(collection, case["id"], point_ids)
    await cases.delete_case(case["id"])

    await ticket_events.append_event(
        ticket["id"], "case_removed", {"case_id": case["id"], "title": case["title"]}
    )
    logger.info("Removed case %s (%s): %d point(s)", case["id"], case["title"], len(point_ids))
    return {**case, "points": len(point_ids)}


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point. One `asyncio.run` per process."""
    return asyncio.run(_main())


async def _main() -> int:
    # Case titles carry an em dash; Windows consoles default both streams to cp1252.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    setup_logging()

    parser = argparse.ArgumentParser(description="Remove a ticket's past case from the knowledge base.")
    parser.add_argument("ticket", help="The ticket reference, e.g. T-14 or 14.")
    args = parser.parse_args()

    try:
        ticket_no = parse_ticket_no(args.ticket)
    except ValueError:
        print(f"Not a ticket reference: {args.ticket!r}. Use T-14 or 14.")
        return 2

    try:
        removed = await delete_ticket_case(ticket_no)
    except (LookupError, ValueError) as exc:
        print(exc)
        return 1
    except Exception:
        logger.exception("Removing the case for T-%d failed", ticket_no)
        return 1

    print(
        f"Removed {removed['title']} (case {removed['id']}): "
        f"{removed['points']} Qdrant point(s), the case row and its chunks."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
