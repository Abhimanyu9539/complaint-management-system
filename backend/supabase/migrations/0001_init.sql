-- 0001_init.sql — schema for the RAG complaint management system
--
-- Tables are created in FK dependency order. Everything here is re-runnable:
-- IF NOT EXISTS on tables/indexes, OR REPLACE on functions, ON CONFLICT on seeds.
--
-- Note: no `vector` extension. Vectors live in Qdrant (build.md §0.5); Postgres is
-- the source of truth for text + metadata, and Qdrant is a rebuildable derivative.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Shared helpers
-- ---------------------------------------------------------------------------

-- Attached to every table carrying updated_at, so the column is maintained by the
-- database rather than trusted to each writer.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS profiles (
    id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email         TEXT NOT NULL,
    display_name  TEXT,
    role          TEXT NOT NULL DEFAULT 'agent' CHECK (role IN ('agent', 'admin')),
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- A signup must always land a profile row, otherwise every FK to profiles(id)
-- breaks for that user. SECURITY DEFINER because auth.users triggers run as the
-- auth admin role, which has no rights on public.profiles.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, display_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data ->> 'display_name', split_part(NEW.email, '@', 1))
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_on_auth_user_created ON auth.users;
CREATE TRIGGER trg_on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Taxonomy
-- ---------------------------------------------------------------------------

-- departments is schema, not data: the 12 slugs are a closed set (build.md D3) and
-- `description` is fed verbatim into the Phase 3 department-classifier prompt.
CREATE TABLE IF NOT EXISTS departments (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    mailbox      TEXT NOT NULL,
    description  TEXT NOT NULL
);

INSERT INTO departments (id, name, mailbox, description) VALUES
    ('warranty', 'Warranty', 'warranty@example.com',
     'Warranty coverage, claims, repairs and replacements for products still under warranty; warranty period disputes and proof-of-purchase issues.'),
    ('billing', 'Billing', 'billing@example.com',
     'Invoices, duplicate or incorrect charges, refunds, payment failures, subscription and pricing disputes.'),
    ('shipping', 'Shipping', 'shipping@example.com',
     'Delivery delays, lost or damaged-in-transit parcels, wrong address, tracking problems and courier escalations.'),
    ('product_safety', 'Product Safety', 'safety@example.com',
     'Injury, fire, overheating, electrical or chemical hazards, and any recall-related report. Highest urgency; may trigger regulatory duties.'),
    ('returns', 'Returns', 'returns@example.com',
     'Return authorisations, exchanges, restocking fees, return-window exceptions and refund-on-return status.'),
    ('tech_support', 'Technical Support', 'support@example.com',
     'Product not working as expected: setup, configuration, firmware, connectivity, error codes and troubleshooting.'),
    ('qa', 'Quality Assurance', 'qa@example.com',
     'Recurring defects, batch or manufacturing quality patterns, and root-cause investigation of product faults.'),
    ('legal', 'Legal', 'legal@example.com',
     'Legal threats, consumer-rights and regulatory claims, data-protection requests, disputes involving liability or compensation.'),
    ('sales', 'Sales', 'sales@example.com',
     'Pre-sales questions, quotes, order changes, bulk and B2B enquiries, promotions and price-match requests.'),
    ('manufacturing', 'Manufacturing', 'manufacturing@example.com',
     'Production defects traced to a specific plant, batch or component; supply and assembly issues.'),
    ('retention', 'Retention', 'retention@example.com',
     'Cancellation requests, churn risk, goodwill gestures and loyalty or compensation offers to keep a customer.'),
    ('spare_parts', 'Spare Parts', 'parts@example.com',
     'Availability, ordering, compatibility and shipment of replacement parts and accessories.')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Knowledge base (source of truth; Qdrant mirrors this)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          TEXT NOT NULL,
    doc_type       TEXT NOT NULL CHECK (doc_type IN ('case', 'policy')),
    department_id  TEXT REFERENCES departments(id),
    category       TEXT,
    source         TEXT NOT NULL DEFAULT 'upload' CHECK (source IN ('seed', 'upload', 'flywheel')),
    storage_path   TEXT,                       -- Supabase Storage key; null for seed-from-disk
    content_hash   TEXT,                       -- lets the pipeline short-circuit unchanged docs
    -- 'deleting' exists so delete/replace can be crash-safe: Qdrant points are removed
    -- first, then Postgres. A crash between the two leaves a visible, resumable row.
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'processing', 'indexed', 'failed', 'deleting')),
    chunk_count    INT NOT NULL DEFAULT 0,
    error          TEXT,
    uploaded_by    UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_documents_status  ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_dept    ON documents(department_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash    ON documents(content_hash);

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    text          TEXT NOT NULL,
    token_count   INT,
    content_hash  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The idempotency key: re-ingesting a document upserts its chunks in place
    -- instead of duplicating them.
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);

-- ---------------------------------------------------------------------------
-- Chat
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON chat_sessions(user_id, updated_at DESC);

DROP TRIGGER IF EXISTS trg_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER trg_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    -- Denormalised from chat_sessions so the RLS policy is a column comparison
    -- rather than a subquery join on every row read.
    user_id           UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role              TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content           TEXT NOT NULL,
    citations         JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{doc_id, chunk_id, title, snippet}]
    langsmith_run_id  TEXT,                                -- feedback attaches to this run
    department        TEXT,                                -- predicted dept for this turn
    no_match          BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

-- ---------------------------------------------------------------------------
-- Ops
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error             TEXT,
    chunk_count       INT NOT NULL DEFAULT 0,
    point_count       INT NOT NULL DEFAULT 0,
    langsmith_run_id  TEXT,
    created_by        UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_document ON ingestion_jobs(document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON ingestion_jobs(status);

-- ---------------------------------------------------------------------------
-- Signal
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS feedback (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id        UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    thumbs            TEXT NOT NULL CHECK (thumbs IN ('up', 'down')),
    comment           TEXT,
    langsmith_run_id  TEXT,                    -- mirrored to LangSmith create_feedback
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One verdict per user per message; changing your mind is an upsert, not a second row.
    UNIQUE (message_id, user_id)
);

-- ---------------------------------------------------------------------------
-- Tickets (D1b: schema now, UI later — adapted from lld.md §3.2 minus email plumbing)
-- ---------------------------------------------------------------------------

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

CREATE TABLE IF NOT EXISTS drafts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id         UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    version           INT NOT NULL,                            -- 1..n per ticket per kind
    kind              TEXT NOT NULL CHECK (kind IN ('customer_reply', 'dept_question')),
    draft_text        TEXT NOT NULL,
    -- retrieved_cases + prompt_version are what make post-hoc failure attribution
    -- possible: did retrieval pick the wrong evidence, or did drafting misuse it?
    retrieved_cases   JSONB NOT NULL DEFAULT '[]'::jsonb,      -- [{chunk_id, doc_id, score}]
    policy_refs       JSONB NOT NULL DEFAULT '[]'::jsonb,
    no_match          BOOLEAN NOT NULL DEFAULT false,
    model             TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    input_tokens      INT,
    output_tokens     INT,
    latency_ms        INT,
    langsmith_run_id  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticket_id, kind, version)
);

CREATE TABLE IF NOT EXISTS draft_feedback (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id     UUID NOT NULL UNIQUE REFERENCES drafts(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    action       TEXT NOT NULL CHECK (action IN ('accepted', 'edited', 'rejected')),
    final_text   TEXT,                                         -- what was actually sent
    edit_reason  TEXT CHECK (edit_reason IN
                 ('wrong_case', 'wrong_tone', 'wrong_policy', 'other')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dept_responses (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id      UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    department_id  TEXT NOT NULL REFERENCES departments(id),
    answer_text    TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dept_responses_ticket ON dept_responses(ticket_id);

-- Append-only audit log. No updated_at by design: rows are never modified.
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
