-- 0007_case_chunks.sql — retrieval units for cases; mirrors the `cases` Qdrant collection.
--
-- A separate table per corpus rather than one polymorphic `chunks` table. The
-- alternatives both cost something real: two nullable FKs make the idempotency
-- key two partial unique indexes, and an untyped (owner_type, owner_id) pair
-- gives up referential integrity *and* the cascade that keeps orphan chunks from
-- accumulating. One FK per table keeps both.
--
-- In practice a case is one chunk (a resolved complaint is semantically atomic —
-- splitting the resolution from the complaint destroys the retrieval unit), but
-- chunk_index is kept so the shape matches policy_chunks and so a future
-- long-case strategy is not a migration.

CREATE TABLE IF NOT EXISTS case_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id       UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    text          TEXT NOT NULL,
    token_count   INT,
    content_hash  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The idempotency key: re-ingesting a case upserts its chunks in place
    -- instead of duplicating them.
    UNIQUE (case_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_case_chunks_case ON case_chunks(case_id);

-- ---------------------------------------------------------------------------
-- RLS — read-only; the pipeline writes as the service role
-- ---------------------------------------------------------------------------
-- Everyone reads chunks: they are the evidence behind citations, and the sources
-- panel is useless without them.

ALTER TABLE case_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_chunks_select_all ON case_chunks;
CREATE POLICY case_chunks_select_all ON case_chunks
    FOR SELECT TO authenticated
    USING (true);
