-- 0025_agent_runs.sql — one row per ticket-graph run, for the admin's Agent activity page.
--
-- Append-only, like ticket_events. `id` is the graph's run_id, which is also the
-- LangSmith root run id, so a row leads straight to its trace.

CREATE TABLE IF NOT EXISTS agent_runs (
    id               UUID PRIMARY KEY,
    ticket_id        UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    ticket_no        BIGINT,
    subject          TEXT,
    trigger          TEXT NOT NULL
                     CHECK (trigger IN ('created', 'dept_response', 'regenerate', 'cli')),
    status           TEXT NOT NULL
                     CHECK (status IN ('succeeded', 'no_match', 'blocked', 'failed')),
    outcome          TEXT,                                   -- ticket status the gate chose
    review_reasons   JSONB NOT NULL DEFAULT '[]'::jsonb,
    predicted_dept   TEXT,
    dept_confidence  REAL,
    category         TEXT,
    grounded         BOOLEAN,
    regenerated      BOOLEAN NOT NULL DEFAULT false,
    precedents_offered INT NOT NULL DEFAULT 0,
    steps            JSONB NOT NULL DEFAULT '[]'::jsonb,     -- [{node, started_at, ms, ok}]
    errors           JSONB NOT NULL DEFAULT '{}'::jsonb,     -- {stage: error}
    latency_ms       INT,
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started ON agent_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status  ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_ticket  ON agent_runs(ticket_id);

-- ---------------------------------------------------------------------------
-- RLS — admins read; writes are service role only
-- ---------------------------------------------------------------------------

ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_runs_select_admin ON agent_runs;
CREATE POLICY agent_runs_select_admin ON agent_runs
    FOR SELECT TO authenticated
    USING (public.is_admin());
