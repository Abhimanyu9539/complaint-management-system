-- 0021_drafts_guard.sql — the output guard's verdict on a ticket draft.
--
-- `grounded` is null when the guardrails were switched off, true when the draft
-- passed, false when it still failed after its one retry. A false draft is kept,
-- not dropped: the agent sees `guard_reasons` next to it, and the gate sends
-- the ticket to review.
--
-- Additive and re-runnable, like every file here.

ALTER TABLE drafts ADD COLUMN IF NOT EXISTS grounded BOOLEAN;

ALTER TABLE drafts ADD COLUMN IF NOT EXISTS guard_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;

-- No RLS changes. 0013's `drafts_all` policy covers rows, so new columns are
-- in scope the moment they exist.
