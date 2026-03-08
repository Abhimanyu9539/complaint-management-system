-- 0015_dept_responses.sql — Path B: what the escalated department answered.
--
-- Feeds `cases.dept_guidance` when the ticket is resolved and minted into a case.

CREATE TABLE IF NOT EXISTS dept_responses (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id      UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    department_id  TEXT NOT NULL REFERENCES departments(id),
    answer_text    TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dept_responses_ticket ON dept_responses(ticket_id);

-- ---------------------------------------------------------------------------
-- RLS — single-team tool: any authenticated agent reads and writes
-- ---------------------------------------------------------------------------

ALTER TABLE dept_responses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS dept_responses_all ON dept_responses;
CREATE POLICY dept_responses_all ON dept_responses
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);
