-- =============================================================================
-- 16: Self-service account deletion (KVKK / GDPR right to erasure)
-- =============================================================================
-- What it does:
--   1. Makes every foreign key from public.* to auth.users ON DELETE CASCADE.
--      Production (2026-11-22, read-only check): favorites.user_id and
--      user_activities.user_id were NO ACTION, so deleting such a user failed even
--      from the Supabase dashboard. Constraints are re-created NOT VALID so existing
--      orphan rows (if any) cannot block the migration; cascading works either way.
--   2. public.delete_my_account(): SECURITY DEFINER, deletes only the caller
--      (auth.uid()); clears books.added_by (the contributed book stays in the shared
--      catalog, the link to the person goes); deleting auth.users cascades to every
--      user table. Callable by `authenticated` only.
--
-- Why an RPC instead of the service-role key in the API: the runtime backend never
-- holds a service_role key (test_catalog_write_boundary.py). This function can only
-- ever delete the account whose JWT calls it.
--
-- Idempotent: safe to run more than once. Rollback: rollbacks/16_account_deletion_rollback.sql
-- =============================================================================

BEGIN;

SET LOCAL lock_timeout = '5s';

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.conname, c.conrelid::regclass AS tbl, a.attname
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.contype = 'f'
          AND c.confrelid = 'auth.users'::regclass
          AND c.connamespace = 'public'::regnamespace
          AND c.confdeltype <> 'c'
          AND array_length(c.conkey, 1) = 1
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES auth.users(id) ON DELETE CASCADE NOT VALID',
            r.tbl, r.conname, r.attname);
        RAISE NOTICE '16: % (%) now ON DELETE CASCADE', r.tbl, r.attname;
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.delete_my_account()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user UUID := auth.uid();
BEGIN
    IF v_user IS NULL THEN
        RAISE EXCEPTION 'not authenticated' USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'books' AND column_name = 'added_by'
    ) THEN
        UPDATE public.books SET added_by = NULL WHERE added_by = v_user;
    END IF;

    DELETE FROM auth.users WHERE id = v_user;
END;
$$;

REVOKE ALL ON FUNCTION public.delete_my_account() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.delete_my_account() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.delete_my_account() TO authenticated;
    END IF;
END $$;

COMMIT;
