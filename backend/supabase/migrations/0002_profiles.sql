-- 0002_profiles.sql — identity, plus the is_admin() helper that reads it.

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
-- RLS — own row, plus admin read-all
-- ---------------------------------------------------------------------------
-- What these policies describe is what a *logged-in agent's* JWT may do. The
-- Supabase secret (service-role) key bypasses RLS entirely — which is why the
-- ingestion pipeline needs no INSERT policies anywhere, and why that key must
-- never reach a browser.

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

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
