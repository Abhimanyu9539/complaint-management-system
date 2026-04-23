-- 0019_rename_ingest_key.sql — `cases.content_hash` / `policies.content_hash`
-- become `ingest_key`.
--
-- The column never held a pure content hash's meaning: it is the key the
-- pipeline's short-circuit compares against, so it must cover the *strategy*
-- (chunk size, overlap, embedding model) as well as the source text. It did
-- not, which made a chunking or model change re-run as `skipped=54` — a silent
-- no-op. `cms.ingestion.transform.cleaner.compute_ingest_key` now folds a
-- per-corpus recipe into it, and the name follows the meaning.
--
-- `case_chunks.content_hash` and `policy_chunks.content_hash` are deliberately
-- NOT renamed. Those are genuine content addresses — they feed `build_point_id`
-- and decide a Qdrant point's identity — and versioning them would re-mint every
-- point id for text nobody edited.
--
-- Existing rows keep their old-format values, which cannot match the new keys,
-- so the first run after this re-ingests the corpus once and then settles back
-- to skipping. That is intended; nothing needs NULLing.
--
-- Additive/altering changes get their own numbered file (the precedent 0017
-- set), and everything here is re-runnable — a bare RENAME COLUMN errors on a
-- second run, hence the existence guards.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'cases' AND column_name = 'content_hash') THEN
        ALTER TABLE cases RENAME COLUMN content_hash TO ingest_key;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'policies' AND column_name = 'content_hash') THEN
        ALTER TABLE policies RENAME COLUMN content_hash TO ingest_key;
    END IF;
END $$;

-- The indexes 0005/0006 created follow the column.
DROP INDEX IF EXISTS idx_cases_hash;
DROP INDEX IF EXISTS idx_policies_hash;
CREATE INDEX IF NOT EXISTS idx_cases_ingest_key    ON cases(ingest_key);
CREATE INDEX IF NOT EXISTS idx_policies_ingest_key ON policies(ingest_key);

-- No RLS changes. Policies grant on rows, not on a column list, so a renamed
-- column stays in scope.
