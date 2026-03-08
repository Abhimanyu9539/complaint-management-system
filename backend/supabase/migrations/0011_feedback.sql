-- 0011_feedback.sql — thumbs on an assistant message.

CREATE TABLE IF NOT EXISTS feedback (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id        UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    thumbs            TEXT NOT NULL CHECK (thumbs IN ('up', 'down')),
    comment           TEXT,
    langsmith_run_id  TEXT,                    -- mirrored to LangSmith create_feedback
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One verdict per user per message; changing your mind is an upsert, not a second row.
    UNIQUE (message_id, user_id)
);

-- ---------------------------------------------------------------------------
-- RLS — strictly own-user
-- ---------------------------------------------------------------------------

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS feedback_own ON feedback;
CREATE POLICY feedback_own ON feedback
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));
