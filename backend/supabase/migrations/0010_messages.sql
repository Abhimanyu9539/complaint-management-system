-- 0010_messages.sql — turns within a chat session.

CREATE TABLE IF NOT EXISTS messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    -- Denormalised from chat_sessions so the RLS policy is a column comparison
    -- rather than a subquery join on every row read.
    user_id           UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role              TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content           TEXT NOT NULL,
    -- [{doc_type, doc_id, chunk_id, title, snippet}]
    --
    -- `doc_type` ('case' | 'policy') is load-bearing, not decorative: with cases
    -- and policies in separate tables there is no single id space left to look a
    -- citation up in. Without the tag the resolver has to probe both tables and
    -- guess, and a stored citation becomes ambiguous the moment ids collide.
    citations         JSONB NOT NULL DEFAULT '[]'::jsonb,
    langsmith_run_id  TEXT,                                -- feedback attaches to this run
    department        TEXT,                                -- predicted dept for this turn
    no_match          BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

-- ---------------------------------------------------------------------------
-- RLS — strictly own-user
-- ---------------------------------------------------------------------------

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS messages_own ON messages;
CREATE POLICY messages_own ON messages
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));
