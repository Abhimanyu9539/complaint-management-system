-- 0008_policy_chunks.sql — retrieval units for policies; mirrors the `policies`
-- Qdrant collection. See 0007_case_chunks.sql for why chunks are split per corpus.
--
-- Unlike cases, a policy genuinely fans out: header-aware split, then a size
-- split, each chunk carrying its heading breadcrumb so a hit can be cited as
-- "Product Warranty Policy > 2. Manufacturing Defects > 2.3" rather than as an
-- anonymous paragraph.

CREATE TABLE IF NOT EXISTS policy_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id     UUID NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    text          TEXT NOT NULL,
    token_count   INT,
    content_hash  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (policy_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_policy ON policy_chunks(policy_id);

-- ---------------------------------------------------------------------------
-- RLS — read-only; the pipeline writes as the service role
-- ---------------------------------------------------------------------------

ALTER TABLE policy_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_chunks_select_all ON policy_chunks;
CREATE POLICY policy_chunks_select_all ON policy_chunks
    FOR SELECT TO authenticated
    USING (true);
