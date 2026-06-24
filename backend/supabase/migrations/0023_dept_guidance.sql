-- 0023_dept_guidance.sql — the department answers a ticket draft was written from.
--
-- `guidance_refs` mirrors `policy_refs`: one row per department answer the drafter
-- was offered, with its `[n]` marker and whether the draft cited it. Empty for a
-- ticket that was never escalated.
--
-- Additive and re-runnable, like every file here.

ALTER TABLE drafts ADD COLUMN IF NOT EXISTS guidance_refs JSONB NOT NULL DEFAULT '[]'::jsonb;

-- No RLS changes. 0013's `drafts_all` policy covers rows, so the new column is
-- in scope the moment it exists.
