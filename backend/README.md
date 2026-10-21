# Complaint Management System — backend

FastAPI service for RAG-based complaint triage and resolution drafting, over
Supabase (documents, chunks, job state) and Qdrant (vectors).

## Layout

The importable code lives under `src/cms/`, a single top-level package:

```
backend/
├── pyproject.toml
├── data/seed/            # fixture corpus (in git, not packaged into the wheel)
├── supabase/migrations/  # applied with the Supabase CLI, not from Python
├── tests/
└── src/cms/
    ├── main.py           # FastAPI app factory -> cms.main:app
    ├── cli/              # console entrypoints (the cms-* commands in pyproject.toml)
    ├── config/           # settings + process bootstrap (trust store, LangSmith env)
    ├── api/              # routers
    ├── db/               # Supabase session + repositories
    ├── ingestion/        # extract -> transform -> load pipeline
    ├── llm/              # embeddings, prompts
    ├── observability/    # tracing, log context ids, Prometheus metrics, LLM usage
    ├── retrieval/        # Qdrant collections + vector store
    ├── rag/, guardrails/, schemas/, services/
```

## Setup

```bash
cd backend
cp .env.example .env      # then fill in real values
uv sync                   # installs deps + this project (editable)
```

`uv sync` installs the project itself, so `cms` is importable and the `cms-*`
commands are on PATH — no `cd backend` requirement and no `sys.path` juggling.

## Running

```bash
uv run uvicorn cms.main:app --reload   # API
uv run cms-create-collections          # create the Qdrant collections
uv run cms-seed --one                  # ingest one case (walking-skeleton check)
uv run cms-seed                        # ingest the full corpus
```

All three are safe to re-run: collection creation is a no-op when the shape
already matches, and the seed run upserts on `source_ref` with a content-hash
short-circuit.

## Configuration

Settings are read from the process environment first, then a `.env` file. The
file is found without depending on the working directory
(`cms.config.settings.resolve_env_file`):

1. `$CMS_ENV_FILE`, if set
2. `.env` in the cwd or any parent directory
3. `backend/.env` in the source tree (editable installs only)

Deployments are expected to pass real environment variables and have no `.env`
at all, which is why "not found" is a log line rather than an error. The
required fields still fail fast at startup if nothing supplies them.

The seed corpus is located the same way — `$SEED_DATA_DIR`, then `./data/seed`
under the cwd, then the source tree. It is deliberately *not* packaged into the
wheel, so a container that needs to re-seed mounts it and sets `SEED_DATA_DIR`.

## Observability

**Logs.** One line per record, as JSON by default. Set `LOG_FORMAT=text` for plain lines in a
terminal and `LOG_LEVEL` for the level. Each line carries the ids that apply:

- `request_id`: the caller's `X-Request-ID` if it is safe to log, otherwise a new one. The same id
  goes back in the response's `X-Request-ID` header. A ticket created by a request keeps the
  request's id through its whole background run.
- `ticket_id` and `run_id`: set for a ticket-graph run. `run_id` is the `agent_runs` id and the
  LangSmith root run id.

The middleware writes one access line per request, with `status` and `duration_ms`. Health probes
and `/metrics` are not logged.

**Metrics.** `GET /metrics` serves Prometheus format:

| Metric | Labels | Use |
|---|---|---|
| `cms_ticket_transitions_total` | `status` | Status funnel. processing_failed rate = `processing_failed` / `processing` |
| `cms_ticket_graph_duration_seconds` | `status` | Graph latency histogram; `_count` is runs by how they ended |
| `cms_guard_checks_total` | `guard`, `result` | Guard failure rate (`blocked` and `error` out of all) |
| `cms_llm_tokens_total` | `model`, `node`, `type` | Tokens per model, for comparing models |
| `cms_llm_cost_usd_total` | `model`, `node` | What OpenRouter billed, for the budget alert |

Token and cost metrics cover every LLM call: the ticket graph, chat, the escalation question and
case minting. Only ticket-graph runs are also saved, per call, in `agent_runs.llm_calls`
(migration 0027). NeMo's rail calls go through `ChatOpenAI`, which reports tokens but no cost.

`/metrics` is public, like `/health`, so restrict it at the network in a deployment. The counters
are per process: with `uvicorn --workers N`, use prometheus_client's multiprocess mode.

**Prometheus.** `docker compose up -d prometheus` scrapes the API on the host every 15s. The UI is
at http://localhost:9090, and the Alerts tab shows the rules in `prometheus/alerts.yml`: daily LLM
budget, processing_failed rate, guard failure rate and graph p95. There is no Alertmanager, so a
firing alert is shown there and sent nowhere. Change a threshold in that file, then restart the
container.

## Flywheel (daily case minting)

Sending a reply no longer mints a case. At 01:00 IST, Airflow takes the tickets resolved the day
before (and still resolved) and mints them one by one. A ticket whose complaint and resolution a
past case already covers is skipped as a duplicate. A similar complaint resolved differently is
still minted. Setup and backfill: [airflow/README.md](airflow/README.md).

## Building

```bash
uv build          # -> dist/*.whl and dist/*.tar.gz
```

The wheel contains `cms` only — `tests/`, `notebooks/`, `data/`, `docs/` and
`supabase/` stay out of it.
