-- 0013_drafts.sql — generated replies awaiting an agent's verdict.

CREATE TABLE IF NOT EXISTS drafts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id         UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    version           INT NOT NULL,                            -- 1..n per ticket per kind
    kind              TEXT NOT NULL CHECK (kind IN ('customer_reply', 'dept_question')),
    draft_text        TEXT NOT NULL,
    -- retrieved_cases + prompt_version are what make post-hoc failure attribution
    -- possible: did retrieval pick the wrong evidence, or did drafting misuse it?
    --
    -- The two evidence columns were already split before the tables were, and
    -- they now line up one-to-one with the corpora they came from — so each
    -- carries its own id name and needs no doc_type tag:
    --   retrieved_cases  [{chunk_id, case_id, score}]    ← cases collection
    --   policy_refs      [{chunk_id, policy_id, score}]  ← policies collection
    --
    -- Scores are NOT comparable between the two columns. BM25 IDF statistics are
    -- computed per Qdrant collection, so the sparse half of each hybrid score is
    -- calibrated against a different corpus. Merge with RRF or take a fixed
    -- top-k from each; sorting the union by raw score silently favours whichever
    -- corpus has the flatter term distribution, and reads as a relevance bug.
    retrieved_cases   JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_refs       JSONB NOT NULL DEFAULT '[]'::jsonb,
    no_match          BOOLEAN NOT NULL DEFAULT false,
    model             TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    input_tokens      INT,
    output_tokens     INT,
    latency_ms        INT,
    langsmith_run_id  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticket_id, kind, version)
);

-- ---------------------------------------------------------------------------
-- RLS — single-team tool: any authenticated agent reads and writes
-- ---------------------------------------------------------------------------

ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS drafts_all ON drafts;
CREATE POLICY drafts_all ON drafts
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);
