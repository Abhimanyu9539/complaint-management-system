-- 0002_rls.sql — Row Level Security on every table.
--
-- What these policies describe: what a *logged-in agent's* JWT may do. The Supabase
-- secret (service-role) key bypasses RLS entirely, which is why the ingestion pipeline
-- needs no INSERT policy on chunks — and why that key must never reach a browser.
--
-- Tenancy model (build.md D2): the knowledge base is shared across the org, while
-- chat sessions, messages and feedback are strictly per-user.
--
-- Re-runnable: DROP POLICY IF EXISTS before each CREATE POLICY.

-- ---------------------------------------------------------------------------
-- Helper
-- ---------------------------------------------------------------------------

-- SECURITY DEFINER so an admin check inside a policy on `profiles` does not
-- re-enter that same policy and recurse. STABLE so it is evaluated once per query.
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = (SELECT auth.uid()) AND role = 'admin' AND is_active
    );
$$;

-- ---------------------------------------------------------------------------
-- Enable RLS everywhere. A single table without it is a hole in the floor.
-- ---------------------------------------------------------------------------

ALTER TABLE profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments     ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents       ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback        ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets         ENABLE ROW LEVEL SECURITY;
ALTER TABLE drafts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE draft_feedback  ENABLE ROW LEVEL SECURITY;
ALTER TABLE dept_responses  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_events   ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- profiles — own row, plus admin read-all
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS profiles_select_own ON profiles;
CREATE POLICY profiles_select_own ON profiles
    FOR SELECT TO authenticated
    USING (id = (SELECT auth.uid()) OR public.is_admin());

-- Role escalation is blocked: the row must still be your own after the update, and
-- `role` is only writable by the service role (no policy grants it).
DROP POLICY IF EXISTS profiles_update_own ON profiles;
CREATE POLICY profiles_update_own ON profiles
    FOR UPDATE TO authenticated
    USING (id = (SELECT auth.uid()))
    WITH CHECK (
        id = (SELECT auth.uid())
        AND role = (SELECT p.role FROM profiles p WHERE p.id = (SELECT auth.uid()))
    );

-- ---------------------------------------------------------------------------
-- departments — read-only taxonomy; writes are migrations (service role)
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS departments_select_all ON departments;
CREATE POLICY departments_select_all ON departments
    FOR SELECT TO authenticated
    USING (true);

-- ---------------------------------------------------------------------------
-- documents / chunks — shared org knowledge base (D2)
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS documents_select_all ON documents;
CREATE POLICY documents_select_all ON documents
    FOR SELECT TO authenticated
    USING (true);

DROP POLICY IF EXISTS documents_insert_own ON documents;
CREATE POLICY documents_insert_own ON documents
    FOR INSERT TO authenticated
    WITH CHECK (uploaded_by = (SELECT auth.uid()));

DROP POLICY IF EXISTS documents_update_own ON documents;
CREATE POLICY documents_update_own ON documents
    FOR UPDATE TO authenticated
    USING (uploaded_by = (SELECT auth.uid()) OR public.is_admin())
    WITH CHECK (uploaded_by = (SELECT auth.uid()) OR public.is_admin());

DROP POLICY IF EXISTS documents_delete_own ON documents;
CREATE POLICY documents_delete_own ON documents
    FOR DELETE TO authenticated
    USING (uploaded_by = (SELECT auth.uid()) OR public.is_admin());

-- Everyone reads chunks (they are the evidence behind citations); nobody writes them
-- but the pipeline, which runs as the service role and bypasses RLS.
DROP POLICY IF EXISTS chunks_select_all ON chunks;
CREATE POLICY chunks_select_all ON chunks
    FOR SELECT TO authenticated
    USING (true);

-- ---------------------------------------------------------------------------
-- chat_sessions / messages / feedback — strictly own-user
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS chat_sessions_own ON chat_sessions;
CREATE POLICY chat_sessions_own ON chat_sessions
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS messages_own ON messages;
CREATE POLICY messages_own ON messages
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS feedback_own ON feedback;
CREATE POLICY feedback_own ON feedback
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

-- ---------------------------------------------------------------------------
-- ingestion_jobs — owner sees own, admin sees all; writes are service role
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS ingestion_jobs_select_own ON ingestion_jobs;
CREATE POLICY ingestion_jobs_select_own ON ingestion_jobs
    FOR SELECT TO authenticated
    USING (created_by = (SELECT auth.uid()) OR public.is_admin());

-- ---------------------------------------------------------------------------
-- Ticket tables — single-team tool: any authenticated agent reads and writes
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS tickets_all ON tickets;
CREATE POLICY tickets_all ON tickets
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS drafts_all ON drafts;
CREATE POLICY drafts_all ON drafts
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS draft_feedback_select_all ON draft_feedback;
CREATE POLICY draft_feedback_select_all ON draft_feedback
    FOR SELECT TO authenticated
    USING (true);

-- Feedback is attributable: you may only record your own verdict on a draft.
DROP POLICY IF EXISTS draft_feedback_write_own ON draft_feedback;
CREATE POLICY draft_feedback_write_own ON draft_feedback
    FOR INSERT TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS draft_feedback_update_own ON draft_feedback;
CREATE POLICY draft_feedback_update_own ON draft_feedback
    FOR UPDATE TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS dept_responses_all ON dept_responses;
CREATE POLICY dept_responses_all ON dept_responses
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- ticket_events — append-only audit
-- ---------------------------------------------------------------------------
-- SELECT and INSERT only. The absence of UPDATE/DELETE policies is the mechanism:
-- with RLS enabled and no policy for a command, that command is denied to everyone
-- except the service role. Do not "fix" this by adding one.

DROP POLICY IF EXISTS ticket_events_select_all ON ticket_events;
CREATE POLICY ticket_events_select_all ON ticket_events
    FOR SELECT TO authenticated
    USING (true);

DROP POLICY IF EXISTS ticket_events_insert ON ticket_events;
CREATE POLICY ticket_events_insert ON ticket_events
    FOR INSERT TO authenticated
    WITH CHECK (actor_id = (SELECT auth.uid()) OR actor_id IS NULL);
