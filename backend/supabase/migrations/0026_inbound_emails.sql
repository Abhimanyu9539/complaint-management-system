-- 0026_inbound_emails.sql — every email n8n posted to the API, and what happened to it.
--
-- `message_id` is UNIQUE: the insert is the dedupe lock, so a re-posted email changes nothing.

CREATE TABLE IF NOT EXISTS inbound_emails (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id    TEXT NOT NULL UNIQUE,
    from_address  TEXT NOT NULL,
    subject       TEXT,
    body_text     TEXT,
    outcome       TEXT NOT NULL DEFAULT 'received'
                  CHECK (outcome IN ('received', 'created', 'dept_answer', 'customer_reply', 'ignored')),
    reason        TEXT,
    ticket_id     UUID REFERENCES tickets(id) ON DELETE SET NULL,
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_received ON inbound_emails(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_ticket   ON inbound_emails(ticket_id);

-- ---------------------------------------------------------------------------
-- RLS — admins read; writes are service role only
-- ---------------------------------------------------------------------------

ALTER TABLE inbound_emails ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS inbound_emails_select_admin ON inbound_emails;
CREATE POLICY inbound_emails_select_admin ON inbound_emails
    FOR SELECT TO authenticated
    USING (public.is_admin());
