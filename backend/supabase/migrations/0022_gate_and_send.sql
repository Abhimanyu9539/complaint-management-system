-- 0022_gate_and_send.sql — what the gate and the send action need.
--
-- `tickets.review_reasons` is why the gate sent a ticket to `needs_review`, in
-- plain words the workbench shows as-is. Empty for a `drafted` ticket.
--
-- `draft_feedback.user_id` becomes nullable: the API has no login yet, so a
-- send or discard has no profile to point at. Null means "an agent, unknown".
-- Put NOT NULL back once JWT verification lands (admin-api.md §9).
--
-- Additive and re-runnable, like every file here.

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS review_reasons JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE draft_feedback ALTER COLUMN user_id DROP NOT NULL;
