-- 0016_ticket_events.sql — append-only audit log.
--
-- No updated_at by design: rows are never modified.

CREATE TABLE IF NOT EXISTS ticket_events (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id   UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    actor_id    UUID REFERENCES profiles(id) ON DELETE SET NULL,   -- null = system
    event       TEXT NOT NULL,   -- created|classified|drafted|sent|escalated|
                                 -- dept_responded|resolved|reopened|assigned|failed
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_ticket ON ticket_events(ticket_id, created_at);

-- ---------------------------------------------------------------------------
-- RLS — SELECT and INSERT only
-- ---------------------------------------------------------------------------
-- The absence of UPDATE/DELETE policies is the mechanism: with RLS enabled and no
-- policy for a command, that command is denied to everyone except the service
-- role. Do not "fix" this by adding one.

ALTER TABLE ticket_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ticket_events_select_all ON ticket_events;
CREATE POLICY ticket_events_select_all ON ticket_events
    FOR SELECT TO authenticated
    USING (true);

DROP POLICY IF EXISTS ticket_events_insert ON ticket_events;
CREATE POLICY ticket_events_insert ON ticket_events
    FOR INSERT TO authenticated
    WITH CHECK (actor_id = (SELECT auth.uid()) OR actor_id IS NULL);
