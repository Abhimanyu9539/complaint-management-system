# Complaint Management System

A RAG system for customer-complaint resolution. Support agents ask it about an incoming
complaint; it retrieves from a knowledge base of **previously resolved cases** and
**company policy documents**, and drafts an answer grounded in what it found — with
citations back to the source, so the agent can check the reasoning before sending
anything to a customer.

The premise is a knowledge flywheel: every complaint resolved (often with guidance from
one of 12 internal departments) becomes a retrievable case, so the same question does not
need to be escalated twice.

## How it works

```
complaint question
        │
        ▼
   analyse ──▶ retrieve ──▶ grade ──▶ generate ──▶ groundedness check
   (intent,    (hybrid       (drop     (cited        (regenerate once,
    dept)       search)       noise)    answer)       else caveat)
                   │
      ┌────────────┴────────────┐
      ▼                         ▼
 cases collection        policies collection
 (what we did before)    (what we're allowed to do)
```

That answer path is the design; the knowledge base underneath it is built and the agent
itself is not yet — see [Status](#status) for exactly where the line falls today.

Two stores, each authoritative for a different thing:

- **Supabase (Postgres)** — the source of truth. Cases, policies, chunks, chat sessions,
  tickets, feedback, ingestion jobs. Row Level Security on every table.
- **Qdrant** — a derived, rebuildable index. Hybrid search per collection: a dense vector
  (`text-embedding-3-small`) for semantic similarity, plus a sparse BM25 vector computed
  locally with `fastembed` for the order numbers, error codes and model names that dense
  embeddings blur.

Everything is reproducible from files: the schema is versioned SQL migrations, the vector
collections are created by an idempotent script, and re-running the ingest is a no-op for
unchanged documents (content hashes short-circuit, and point ids are `uuid5`-derived).

### Two corpora, not one

`cases` and `policies` are deliberately separate tables backed by separate Qdrant
collections, because they differ in origin, governance and chunking:

|              | `cases`                          | `policies`                              |
| ------------ | -------------------------------- | --------------------------------------- |
| origin       | seed corpus, or a resolved ticket | authored and uploaded                   |
| chunking     | 1 case = 1 chunk                 | header split, then ~800 tok / 100 overlap |
| governance   | none — a record of what happened | lifecycle: draft → published → superseded |

The consequence worth knowing before writing retrieval: **the collection is the
discriminator**, and BM25 IDF is computed per collection — so scores from the two are not
comparable and must be merged with RRF rather than sorted as a union. See
[backend/supabase/migrations/README.md](backend/supabase/migrations/README.md).

## Layout

```
complaint-management-system/
├── backend/     FastAPI service, ingestion pipeline, migrations  (Python 3.13, uv)
└── frontend/    Chat UI                                          (React 19, Vite, Tailwind)
```

The backend is an installable package (`src/cms/`) with console entrypoints — see
[backend/README.md](backend/README.md) for its layout, configuration resolution and build.

## Quickstart

**Prerequisites:** Python 3.13 + [uv](https://docs.astral.sh/uv/), Node 20+, a Supabase
project, a Qdrant instance (local Docker or Cloud), and OpenAI + LangSmith API keys.

```bash
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### Backend

```bash
cd backend
cp .env.example .env          # fill in real values
uv sync                       # installs deps + the project itself (editable)

supabase link --project-ref <ref> && supabase db push   # apply the 16 migrations

uv run cms-create-collections # create the two Qdrant collections
uv run cms-seed --one         # ingest one case end to end (the walking-skeleton check)
uv run cms-seed               # then the full corpus: 20 cases + 34 policies

uv run uvicorn cms.main:app --reload
```

`GET /health` is a liveness check; `GET /health/deps` pings Supabase and Qdrant and reports
each separately, which is the fastest way to tell a broken `.env` from a broken service.

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The admin panel (`/admin`) is real-only and always calls `VITE_API_BASE_URL`
(defaults to `http://localhost:8000`) — start the backend first. Chat has its
own switch and **runs mocked by default** (`VITE_CHAT_USE_MOCK=true`):
realistic streamed responses and localStorage sessions, no backend required,
since no chat backend exists yet. Set `VITE_CHAT_USE_MOCK=false` once one does.

## Configuration

Every backend setting is a typed field on one `Settings` class, read from the environment
first and then a `.env` file; secrets have no defaults, so a missing one fails at startup
rather than on the first request that needs it. Placeholders and comments for each are in
[backend/.env.example](backend/.env.example); the resolution order for `.env` itself is in
[backend/README.md](backend/README.md#configuration).

## Status

Built and working end to end:

- Config, logging and process bootstrap — OS trust store injection, LangSmith env export
- FastAPI app with health and dependency-probe endpoints
- 16 Supabase migrations, one table per file, RLS enabled and policied on each
- Idempotent creation of both Qdrant collections — named dense + sparse vectors with the
  BM25 IDF modifier, plus the payload indexes retrieval filters on
- The ingestion pipeline: extract → clean/chunk/enrich → chunk rows in Postgres → one
  batched embedding call → Qdrant upsert, wrapped in a single LangSmith trace
- A 54-document synthetic seed corpus and its runner, modelling an Indian D2C e-commerce
  brand: 20 resolved cases, 18 department-scoped policies across the 12 departments, and
  16 company-wide policies (SLA, escalation, approval authority, PII/DPDP, AI-drafting
  governance, statutory grievance redressal) that the department policies cross-reference
  rather than restate
- The chat UI: streaming messages, expandable citation chips, a citations panel, session
  sidebar, themes — currently against the mock transport

Not yet built:

- The LangGraph agent (`rag/`, `guardrails/` are stubs) and the hybrid retriever on top of
  the vector store
- The API surface beyond health — chat/SSE, sessions, documents, feedback — and Supabase
  JWT auth
- The golden dataset and LangSmith eval harness
- Frontend auth, and wiring it to the real backend

All LLM and embedding calls go through LangChain rather than the raw OpenAI SDK, which is
what makes LangSmith tracing automatic.
