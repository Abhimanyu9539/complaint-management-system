-- 0014_draft_feedback.sql — what the agent actually did with a draft.
--
-- This is the flywheel's input signal: an 'accepted' or lightly-'edited' draft on
-- a resolved ticket is what earns that ticket a row in `cases`.

CREATE TABLE IF NOT EXISTS draft_feedback (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id     UUID NOT NULL UNIQUE REFERENCES drafts(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    action       TEXT NOT NULL CHECK (action IN ('accepted', 'edited', 'rejected')),
    final_text   TEXT,                                         -- what was actually sent
    edit_reason  TEXT CHECK (edit_reason IN
                 ('wrong_case', 'wrong_tone', 'wrong_policy', 'other')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- RLS — everyone reads, you may only record your own verdict
-- ---------------------------------------------------------------------------

ALTER TABLE draft_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS draft_feedback_select_all ON draft_feedback;
CREATE POLICY draft_feedback_select_all ON draft_feedback
    FOR SELECT TO authenticated
    USING (true);

DROP POLICY IF EXISTS draft_feedback_write_own ON draft_feedback;
CREATE POLICY draft_feedback_write_own ON draft_feedback
    FOR INSERT TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS draft_feedback_update_own ON draft_feedback;
CREATE POLICY draft_feedback_update_own ON draft_feedback
    FOR UPDATE TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));
