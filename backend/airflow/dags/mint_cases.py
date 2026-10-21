"""Daily flywheel: mint yesterday's (IST) resolved tickets into past cases, one at a time.

Plumbing only: the API decides what is minted, refreshed or skipped as a duplicate.
"""

import logging
import os
from datetime import timedelta

import httpx
import pendulum
from airflow.sdk import Param, dag, get_current_context, task

logger = logging.getLogger(__name__)

API_URL = os.environ.get("CMS_API_URL", "http://host.docker.internal:8000")
JOB_SECRET = os.environ.get("FLYWHEEL_JOB_SECRET", "")
TIMEZONE = "Asia/Kolkata"
LIST_TIMEOUT_SECONDS = 30
# One mint runs the summary, the duplicate judge and the ingest.
MINT_TIMEOUT_SECONDS = 120
# What the API answers for each ticket (`MintOutcome`).
OUTCOMES = ("minted", "duplicate", "skipped")


def _run_day() -> str:
    """The IST day this run covers: `params.day`, or the day before the run."""
    context = get_current_context()
    day = context["params"].get("day")
    if day:
        return day
    run_after = pendulum.instance(context["dag_run"].run_after).in_timezone(TIMEZONE)
    return run_after.subtract(days=1).to_date_string()


def _call(method: str, path: str, timeout: int, **kwargs) -> dict:
    """One API call. A down API is named plainly, not as httpx's IPv6 'Network is unreachable'."""
    try:
        response = httpx.request(
            method, f"{API_URL}{path}", headers={"X-Job-Secret": JOB_SECRET}, timeout=timeout, **kwargs
        )
    except httpx.ConnectError as exc:
        raise RuntimeError(f"Cannot reach the API at {API_URL}: is it running?") from exc
    response.raise_for_status()
    return response.json()


@dag(
    schedule="0 1 * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    params={"day": Param(None, type=["null", "string"], format="date", description="IST day to mint")},
    tags=["flywheel"],
)
def mint_cases():
    @task(retries=3, retry_delay=timedelta(minutes=5))
    def list_resolved() -> list[str]:
        """The tickets resolved on the run's day, oldest first."""
        day = _run_day()
        result = _call("GET", "/api/v1/flywheel/candidates", LIST_TIMEOUT_SECONDS, params={"day": day})
        ticket_ids = result["ticket_ids"]
        logger.info("Day %s: %d resolved ticket(s) to mint", day, len(ticket_ids))
        return ticket_ids

    # One at a time, so a case minted earlier in the run is seen by the next duplicate check.
    @task(retries=3, retry_delay=timedelta(minutes=5), max_active_tis_per_dag=1)
    def mint(ticket_id: str) -> dict:
        result = _call("POST", f"/api/v1/flywheel/tickets/{ticket_id}/mint", MINT_TIMEOUT_SECONDS)
        logger.info("Ticket %s: %s (%s)", ticket_id, result["outcome"], result.get("reason") or "")
        return result

    # Runs unless a mint failed, including on a day with no tickets (`mint` is then skipped).
    @task(trigger_rule="none_failed")
    def summarise(ticket_ids: list[str], results) -> dict:
        """One line per run: how many tickets, and what happened to them."""
        day = _run_day()
        outcomes = [result["outcome"] for result in results] if ticket_ids else []
        summary = {"day": day, "tickets": len(ticket_ids)} | {o: outcomes.count(o) for o in OUTCOMES}

        if not ticket_ids:
            logger.info("Day %s: nothing to mint", day)
        else:
            logger.info(
                "Day %s: %d ticket(s), %d minted, %d duplicate, %d skipped",
                day,
                summary["tickets"],
                summary["minted"],
                summary["duplicate"],
                summary["skipped"],
            )
        return summary

    ticket_ids = list_resolved()
    summarise(ticket_ids, mint.expand(ticket_id=ticket_ids))


mint_cases()
