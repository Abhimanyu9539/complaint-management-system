"""CLI entrypoint for running the ticket graph on stored tickets and saving the result.

Usage (from anywhere, once the project is installed):

    cms-triage 3f2c...-ticket-uuid
    cms-triage --unclassified        # backfill every ticket with no predicted_dept
"""

import argparse
import asyncio
import logging
import sys

# The `cms.config` import must come first: importing it runs cms/config/__init__.py,
# which injects the OS trust store into ssl. That has to happen before any HTTPS
# client (openai, supabase) is constructed.
from cms.config.logging_config import setup_logging
from cms.db.repositories.tickets import list_unclassified_ticket_ids
from cms.services.ticket_pipeline import process_ticket

logger = logging.getLogger("cms.cli.triage")


def main() -> int:
    """Sync shell for the `[project.scripts]` entry point.

    Exactly one `asyncio.run` per process: the cached supabase client binds its
    connection pool to the loop it creates.
    """
    return asyncio.run(_main())


async def _main() -> int:
    setup_logging()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Run the ticket graph on stored tickets and save the classification."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("ticket_id", nargs="?", help="One ticket's id.")
    target.add_argument(
        "--unclassified", action="store_true", help="Every ticket with no predicted department."
    )
    args = parser.parse_args()

    try:
        ticket_ids = await list_unclassified_ticket_ids() if args.unclassified else [args.ticket_id]
    except Exception:
        logger.exception("Could not list the tickets to triage")
        return 1

    # One at a time: a backfill is not worth a burst of parallel model calls.
    # `process_ticket` never raises; each outcome is in the log and the ticket's events.
    for ticket_id in ticket_ids:
        await process_ticket(ticket_id)
    print(f"Triaged {len(ticket_ids)} ticket(s). Check each ticket's events for the outcome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
