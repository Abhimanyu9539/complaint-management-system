# Complaint Management System — backend

FastAPI service for RAG-based complaint triage and resolution drafting, over
Supabase (documents, chunks, job state) and Qdrant (vectors).

## Layout

The importable code lives under `src/cms/`, a single top-level package:

```
backend/
├── pyproject.toml
├── data/seed/            # fixture corpus (git-ignored, not packaged)
├── supabase/migrations/  # applied with the Supabase CLI, not from Python
├── tests/
└── src/cms/
    ├── main.py           # FastAPI app factory -> cms.main:app
    ├── cli/              # console entrypoints (cms-seed, cms-create-collections, cms-analyze)
    ├── config/           # settings + process bootstrap (trust store, LangSmith env)
    ├── api/              # routers
    ├── db/               # Supabase session + repositories
    ├── ingestion/        # extract -> transform -> load pipeline
    ├── llm/              # embeddings, prompts
    ├── observability/    # tracing setup
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
under the cwd, then the source tree. It is deliberately *not* packaged: it is
git-ignored fixture data, so a container that needs to re-seed mounts it and
sets `SEED_DATA_DIR`.

## Building

```bash
uv build          # -> dist/*.whl and dist/*.tar.gz
```

The wheel contains `cms` only — `tests/`, `notebooks/`, `data/`, `docs/` and
`supabase/` stay out of it.
