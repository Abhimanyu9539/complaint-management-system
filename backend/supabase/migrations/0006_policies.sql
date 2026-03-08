-- 0006_policies.sql — authored policy documents, the normative half of the
-- knowledge base. See 0005_cases.sql for why this is a separate table.
--
-- Two independent state machines, deliberately kept in two columns:
--
--   status     — is this indexed in Qdrant?      (ingestion)
--   lifecycle  — is this approved for use?       (governance)
--
-- They are orthogonal: a published policy that gets edited returns to
-- status='pending' while staying lifecycle='published'. Merging them into one
-- column produces a CHECK constraint holding two unrelated vocabularies, where
-- most values are illegal in most states — a constraint that has stopped
-- constraining. Retrieval filters on lifecycle; the pipeline drives status.

CREATE TABLE IF NOT EXISTS policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    department_id   TEXT REFERENCES departments(id),  -- NULL = applies org-wide
    version         TEXT,
    effective_date  DATE,
    -- Self-reference rather than a deletion: superseded policies stay readable,
    -- because a case resolved last year was resolved under the old wording and
    -- an agent auditing it needs to see that wording.
    supersedes      UUID REFERENCES policies(id) ON DELETE SET NULL,
    lifecycle       TEXT NOT NULL DEFAULT 'draft'
                    CHECK (lifecycle IN ('draft', 'in_review', 'published',
                                         'superseded', 'archived')),

    storage_path    TEXT,                       -- Supabase Storage key; NULL for seed-from-disk
    mime_type       TEXT,
    source          TEXT NOT NULL DEFAULT 'upload' CHECK (source IN ('seed', 'upload')),

    -- Ingestion lifecycle; same vocabulary and same crash-safety rationale as
    -- cases.status, but driven independently — the two corpora index separately.
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'indexed', 'failed', 'deleting')),
    content_hash    TEXT,
    chunk_count     INT NOT NULL DEFAULT 0,
    error           TEXT,

    uploaded_by     UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_policies_status    ON policies(status);
CREATE INDEX IF NOT EXISTS idx_policies_lifecycle ON policies(lifecycle);
CREATE INDEX IF NOT EXISTS idx_policies_dept      ON policies(department_id);
CREATE INDEX IF NOT EXISTS idx_policies_hash      ON policies(content_hash);

DROP TRIGGER IF EXISTS trg_policies_updated_at ON policies;
CREATE TRIGGER trg_policies_updated_at
    BEFORE UPDATE ON policies
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS — everyone reads, admins write
-- ---------------------------------------------------------------------------
-- Stricter than the old shared-documents rule, which let any authenticated agent
-- insert. A policy document is the thing drafts are checked *against*; if an
-- agent can add one, they can manufacture the authority for their own reply.
-- Loosen this to `uploaded_by = auth.uid()` only if policy authoring is meant to
-- be self-serve.

ALTER TABLE policies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policies_select_all ON policies;
CREATE POLICY policies_select_all ON policies
    FOR SELECT TO authenticated
    USING (true);

DROP POLICY IF EXISTS policies_write_admin ON policies;
CREATE POLICY policies_write_admin ON policies
    FOR ALL TO authenticated
    USING (public.is_admin())
    WITH CHECK (public.is_admin());
