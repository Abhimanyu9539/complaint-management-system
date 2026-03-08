-- 0004_tickets.sql — the live complaint queue (D1b: schema now, UI later —
-- adapted from lld.md §3.2 minus email plumbing).
--
-- Runs before `cases` because a resolved ticket is what a case is *made from*:
-- cases.ticket_id points back here, closing the flywheel loop.

CREATE TABLE IF NOT EXISTS tickets (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_no        BIGINT GENERATED ALWAYS AS IDENTITY,      -- human ref, e.g. T-1042
    status           TEXT NOT NULL DEFAULT 'new' CHECK (status IN
                     ('new', 'processing', 'drafted', 'needs_review', 'escalated',
                      'dept_responded', 'resolved', 'processing_failed')),
    severity         TEXT NOT NULL DEFAULT 'normal' CHECK (severity IN
                     ('low', 'normal', 'high', 'critical')),
    subject          TEXT NOT NULL,
    customer_email   TEXT,                                     -- nullable: pasted complaints may lack it
    predicted_dept   TEXT REFERENCES departments(id),
    dept_confidence  REAL,
    escalated_dept   TEXT REFERENCES departments(id),          -- actual dept = the label source
    category         TEXT,
    entities         JSONB NOT NULL DEFAULT '{}'::jsonb,       -- {order_no, product, error_code, ...}
    assignee_id      UUID REFERENCES profiles(id) ON DELETE SET NULL,
    resolution_path  TEXT CHECK (resolution_path IN ('direct', 'escalated')),  -- Path A/B
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tickets_status  ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at DESC);

DROP TRIGGER IF EXISTS trg_tickets_updated_at ON tickets;
CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS — single-team tool: any authenticated agent reads and writes
-- ---------------------------------------------------------------------------

ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tickets_all ON tickets;
CREATE POLICY tickets_all ON tickets
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);
