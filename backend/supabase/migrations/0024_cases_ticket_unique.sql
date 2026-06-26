-- 0024_cases_ticket_unique.sql — at most one flywheel case per ticket.
--
-- A case is minted from a ticket when its reply is sent. Keying the upsert on
-- `ticket_id` makes that idempotent: re-sending a reopened ticket updates its
-- case instead of adding a second one. Seed cases have no ticket, and NULLs
-- stay distinct under UNIQUE, so they are unaffected.
--
-- Re-runnable, like every file here: the constraint is added only if missing.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'cases_ticket_id_key'
    ) THEN
        ALTER TABLE cases ADD CONSTRAINT cases_ticket_id_key UNIQUE (ticket_id);
    END IF;
END $$;
