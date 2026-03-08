-- 0012_ingestion_jobs.sql — one row per ingest attempt, across both corpora.
--
-- Deliberately *not* split per corpus, and deliberately without an FK on
-- document_id. This is an append-only ops log: its whole value is answering
-- "what failed, across everything, in the last hour" in one query, which two
-- tables would turn into a UNION that every new ops metric has to be written
-- into twice. The cost is that document_id cannot be a foreign key — it points
-- into cases *or* policies depending on doc_type, and Postgres has no way to
-- express that. For a log whose rows outlive the documents they describe (a
-- failed ingest of a since-deleted document is still evidence), that trade is
-- the right way round: no cascade means the history survives.
--
-- Because there is no FK, document_id may reference a row that no longer exists.
-- Readers must LEFT JOIN, never INNER JOIN.

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type          TEXT NOT NULL CHECK (doc_type IN ('case', 'policy')),
    document_id       UUID NOT NULL,           -- cases.id or policies.id, per doc_type
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error             TEXT,
    chunk_count       INT NOT NULL DEFAULT 0,
    point_count       INT NOT NULL DEFAULT 0,
    langsmith_run_id  TEXT,
    created_by        UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_document ON ingestion_jobs(doc_type, document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON ingestion_jobs(status);

-- ---------------------------------------------------------------------------
-- RLS — owner sees own, admin sees all; writes are service role
-- ---------------------------------------------------------------------------

ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ingestion_jobs_select_own ON ingestion_jobs;
CREATE POLICY ingestion_jobs_select_own ON ingestion_jobs
    FOR SELECT TO authenticated
    USING (created_by = (SELECT auth.uid()) OR public.is_admin());
