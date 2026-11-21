-- =============================================================================
-- [DRAFT / NOT APPLIED TO PRODUCTION]
-- ROLLBACK 01c: CATALOG WRITE LOCKDOWN
-- =============================================================================
-- File: backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown_rollback.sql
--
-- Restores the table grants 01c removed (Supabase's default API-role grants:
-- INSERT, UPDATE, DELETE, REFERENCES, TRIGGER for anon and authenticated).
--
-- Fail-safe by design — it does NOT restore:
--   * TRUNCATE (bypasses RLS; removed by 01_PROD and never given back), or
--   * the permissive policies "python_ekleme_izni" / "python_guncelleme_izni".
-- With RLS enabled and only SELECT policies, the restored grants still let no
-- client write a catalog row. Re-creating those policies would reopen the hole
-- and is intentionally left out. Ingestion runs as service_role and does not
-- need them.
--
-- Do not use 01b_DRAFT_least_privilege_and_policy_cleanup_rollback.sql to undo
-- 01c: that file re-creates both permissive policies.
-- =============================================================================

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

GRANT INSERT, UPDATE, DELETE, REFERENCES, TRIGGER
    ON TABLE public.books, public.book_embeddings
    TO anon, authenticated;

GRANT SELECT ON TABLE public.books, public.book_embeddings TO anon, authenticated;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename IN ('books', 'book_embeddings') AND cmd <> 'SELECT'
    ) THEN
        RAISE WARNING '01c ROLLBACK: a non-SELECT policy exists on books/book_embeddings; with the restored grants it may allow client writes. Review pg_policies.';
    END IF;
END $$;

COMMIT;
