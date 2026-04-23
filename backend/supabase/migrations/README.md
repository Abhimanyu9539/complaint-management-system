# Migrations

One file per table. Each file is self-contained: the `CREATE TABLE`, its indexes,
its triggers and its RLS policies live together, so a table's grants cannot drift
away from the table they protect. Everything is re-runnable — `IF NOT EXISTS` on
tables and indexes, `OR REPLACE` on functions, `DROP … IF EXISTS` before each
trigger and policy, `ON CONFLICT` on seeds.

Files run in filename order, which is FK dependency order.

| File | Table | Notes |
|---|---|---|
| `0001_extensions.sql` | — | `pgcrypto`, `set_updated_at()` |
| `0002_profiles.sql` | `profiles` | also `handle_new_user()`, `is_admin()` |
| `0003_departments.sql` | `departments` | closed set of 12, seeded here |
| `0004_tickets.sql` | `tickets` | before `cases` — a case cites its ticket |
| `0005_cases.sql` | `cases` | resolved complaints |
| `0006_policies.sql` | `policies` | authored documents |
| `0007_case_chunks.sql` | `case_chunks` | → `cases` Qdrant collection |
| `0008_policy_chunks.sql` | `policy_chunks` | → `policies` Qdrant collection |
| `0009_chat_sessions.sql` | `chat_sessions` | |
| `0010_messages.sql` | `messages` | `citations` carries `doc_type` |
| `0011_feedback.sql` | `feedback` | |
| `0012_ingestion_jobs.sql` | `ingestion_jobs` | spans both corpora; no FK by design |
| `0013_drafts.sql` | `drafts` | |
| `0014_draft_feedback.sql` | `draft_feedback` | |
| `0015_dept_responses.sql` | `dept_responses` | |
| `0016_ticket_events.sql` | `ticket_events` | append-only |
| `0017_tickets_web_intake.sql` | `tickets` | adds `body` + `source`; the first file to alter an existing table |
| `0018_policy_files_bucket.sql` | — | creates the private `policy-files` Storage bucket seeded policies upload into |
| `0019_rename_ingest_key.sql` | `cases`, `policies` | `content_hash` → `ingest_key`; the chunk tables keep `content_hash` |

`0017` breaks the "one file per table" rule in the only way that keeps it
meaningful: `0004` is the file that *creates* `tickets`, and editing it in place
would make a re-run of the set silently disagree with a database migrated
earlier. Additive columns arrive as their own numbered file.

## Two corpora, not one

`cases` and `policies` are separate tables backed by **separate Qdrant
collections**. They are not two flavours of one thing:

| | `cases` | `policies` |
|---|---|---|
| origin | seed corpus, or minted from a resolved ticket | authored, uploaded |
| written by | service role only (flywheel) | admins |
| chunking | 1 case = 1 chunk | header split, then ~800 tok / 100 overlap |
| governance | none — a case is a record of what happened | `lifecycle` (draft → published → superseded) |
| Qdrant | `cases` collection | `policies` collection |

Consequences worth knowing before writing retrieval:

- **The collection is the discriminator.** Retrieval picks a collection rather
  than filtering `doc_type`, so `doc_type` is not an indexed payload field in
  either collection. Point id spaces are physically separate, so a stale-point
  delete filtered on `metadata.doc_id` can no longer reach across corpora.
- **BM25 IDF is computed per collection.** The sparse half of each hybrid score
  is calibrated against a different corpus, so scores from the two collections
  are not comparable. Merge with RRF, or take a fixed top-k from each — sorting
  the union by raw score systematically favours whichever corpus has the flatter
  term distribution.
- **Stored citations need `doc_type`.** With no shared id space, `messages.citations`
  cannot be resolved from `doc_id` alone. `drafts.retrieved_cases` /
  `drafts.policy_refs` were already split by corpus and instead carry `case_id` /
  `policy_id` directly.

## Not yet updated

The schema landed first; these still speak the old single-`documents` shape and
need to follow:

- `backend/app/ingestion/pipeline.py` — table + collection are now parameters
- `backend/app/services/vector_store.py` — `get_vector_store()` takes a collection
- `backend/app/config.py` — one collection setting becomes two
- `backend/scripts/create_qdrant_collection.py` — creates two collections
- `backend/scripts/seed.py` — writes structured case columns instead of a blob
- `frontend/src/lib/chat/` — `GET /documents/{id}` splits by `doc_type`
