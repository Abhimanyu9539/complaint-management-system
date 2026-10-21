# Daily case minting

Airflow runs `dags/mint_cases.py` every day at 01:00 IST. It makes no decisions: the API
decides what is minted, refreshed or skipped.

```
Airflow DAG mint_cases (X-Job-Secret)
  list_resolved → GET  /api/v1/flywheel/candidates?day=YYYY-MM-DD
  mint (one task per ticket, one at a time, 3 retries)
                → POST /api/v1/flywheel/tickets/{id}/mint
```

For each ticket, the API:

1. Skips it if it is no longer resolved, has no sent reply, or has no department.
2. Refreshes its case if it already has one (a reopened ticket resolved again).
3. Otherwise searches the past cases. For each case that scores at least
   `FLYWHEEL_SIMILAR_CASE_THRESHOLD` (0.70), the cheap model judges whether it is the
   same complaint resolved the same way.
4. If it is, the ticket is skipped and its timeline shows "Similar case already in the
   knowledge base". If not, the case is minted.

A failed mint answers 500, so Airflow retries it.

## Setup

1. Make a secret:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Add it to `backend/.env`:

   ```
   FLYWHEEL_JOB_SECRET=<that value>
   ```

3. Restart the API. Until the secret is set, the endpoints answer 503.

4. Start Airflow from `backend/`:

   ```powershell
   docker compose up -d airflow
   ```

5. Open http://localhost:8080. No login is needed. The `mint_cases` DAG appears within a
   minute.

## Run it now, or for an earlier day

1. In the Airflow UI, open `mint_cases` and click **Trigger**.
2. Set `day` to the IST date to mint, for example `2026-11-07`. Leave it empty for
   yesterday.
3. Open the run, then the `summarise` task's **Logs**. They show one line for the run:
   `Day 2026-11-07: 3 ticket(s), 2 minted, 1 duplicate, 0 skipped`, or
   `Day 2026-11-07: nothing to mint`. The same counts are under its **XCom**.
4. For one ticket's details, open `mint` → **Mapped Tasks**: each entry's log shows that
   ticket's outcome and reason.

`summarise` runs unless a mint failed. If a ticket fails after its 3 retries, the run
turns red and `summarise` shows *upstream failed*; the failed entry is under `mint` →
**Mapped Tasks**.

Check what a day would mint without running it:

```powershell
curl.exe -H "X-Job-Secret: <secret>" "http://localhost:8000/api/v1/flywheel/candidates?day=2026-11-07"
```

Mint one ticket by hand:

```powershell
curl.exe -X POST -H "X-Job-Secret: <secret>" "http://localhost:8000/api/v1/flywheel/tickets/<ticket id>/mint"
```

## Tuning

The API log has a `Duplicate check:` line for each past case, with its score and the
judge's verdict. Raise `FLYWHEEL_SIMILAR_CASE_THRESHOLD` if the judge is shown unrelated
cases. The `cms_flywheel_outcomes_total{outcome}` metric counts minted, duplicate,
skipped and failed tickets.
