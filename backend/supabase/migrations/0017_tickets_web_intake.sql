-- 0017_tickets_web_intake.sql — what `tickets` needs to accept a complaint
-- submitted from the web form rather than ingested from a mailbox.
--
-- 0004 adapted lld.md §3.2 "minus email plumbing", and the complaint *body* was
-- part of that plumbing: in the original design the text lived on the email row
-- the ticket pointed at, so `tickets` carries only a `subject`. With no email
-- pipeline and a customer typing directly into a form, there is nowhere to put
-- what they wrote. This adds it.
--
-- Additive and re-runnable, like every file here.

-- Nullable on purpose. The DB permits what the domain permits — a complaint
-- pasted from a phone call may legitimately be subject-only — and the API
-- enforces the stricter rule (body required) for web submissions, where an
-- empty complaint is a bug in the form rather than a fact about the world.
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS body TEXT;

-- Where the ticket came from, mirroring the `source` CHECK columns already on
-- `cases` and `policies`. Defaults to 'web' because that is the only writer
-- today; 'email' is reserved for the n8n/Graph intake in a later phase, and
-- 'agent' for a ticket an internal user opens on a customer's behalf.
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'web'
    CHECK (source IN ('email', 'web', 'agent'));

-- The escalation-rate metric filters on `resolution_path IS NOT NULL` and
-- groups by its value (lld.md:257 — "resolution_path is the column the
-- escalation-rate metric reads"). It is a low-cardinality column on a table
-- that only grows, so the index earns itself as soon as the dashboard polls.
CREATE INDEX IF NOT EXISTS idx_tickets_resolution ON tickets(resolution_path);

-- No RLS changes. 0004's `tickets_all` policy already covers these columns —
-- policies grant on rows, not on the column list, so a new column is in scope
-- the moment it exists.
