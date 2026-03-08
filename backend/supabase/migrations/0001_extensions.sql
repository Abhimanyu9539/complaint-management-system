-- 0001_extensions.sql — extensions and cross-table helpers.
--
-- Layout: migrations run in filename order and each file is self-contained —
-- one table, with its indexes, triggers and RLS policies together. Grants that
-- live in a separate file drift away from the table they protect, so they do
-- not. This file holds only what more than one table needs, and runs first.
--
-- Numbering follows FK dependency order, which is why `tickets` (0004) precedes
-- `cases` (0005): a case carries the ticket it was resolved from.
--
-- Note: no `vector` extension. Vectors live in Qdrant, in two collections — one
-- for cases, one for policies. Postgres is the source of truth for text and
-- metadata; each Qdrant collection is a rebuildable derivative of one table.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Shared helpers
-- ---------------------------------------------------------------------------

-- Attached to every table carrying updated_at, so the column is maintained by
-- the database rather than trusted to each writer.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- public.is_admin() is the other shared helper, but it reads public.profiles and
-- LANGUAGE sql bodies are validated at CREATE time — so it is defined in
-- 0002_profiles.sql, immediately after the table it queries.
