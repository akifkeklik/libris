-- =============================================================================
-- [DRAFT / NOT APPLIED TO PRODUCTION]
-- 01c: CATALOG WRITE LOCKDOWN — public.books, public.book_embeddings
-- =============================================================================
-- File: backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown.sql
-- Rollback: 01c_DRAFT_catalog_write_lockdown_rollback.sql
-- Verify:   verify_01c_catalog_write_lockdown.sql (read-only, run after apply)
-- Test:     test_01c_catalog_write_lockdown_runtime.sql (CI, SET ROLE anon/authenticated)
--
-- Why a separate file from 01b_DRAFT:
--   01b_DRAFT bundles the catalog fix with DML changes on four user tables
--   (favorites, user_activities, user_interactions, user_profiles), and its
--   rollback re-creates the anonymous write policies. This file touches only
--   the two shared catalog tables, so it can be reviewed, applied and rolled
--   back on its own.
--
-- Production state this file was written against (audit, 2026-11-21):
--   * public.books is owned by postgres; relforcerowsecurity = false.
--   * add_catalog_book is owned by postgres and is SECURITY DEFINER, so reader
--     contributions insert as the table owner and do not need any client grant
--     or INSERT policy on public.books.
--   * match_query_embeddings is SECURITY INVOKER, so anon/authenticated must
--     keep SELECT on public.book_embeddings (and on public.books).
--   * anon and authenticated hold INSERT, UPDATE, DELETE on both tables.
--   * Ingestion/backfill scripts write as service_role or postgres, which this
--     file does not touch.
--
-- What it does:
--   1. Drops the two permissive write policies on public.books
--      ("python_ekleme_izni" INSERT WITH CHECK true,
--       "python_guncelleme_izni" UPDATE USING true).
--   2. Revokes from anon, authenticated and PUBLIC on both tables:
--        INSERT, UPDATE, DELETE  — clients never write the catalog directly.
--        REFERENCES              — would let a role that can run DDL add a
--                                  foreign key to the catalog and block the
--                                  owner's UPDATE/DELETE of catalog rows.
--        TRIGGER                 — would let a role that can run DDL attach a
--                                  trigger that then runs inside every write
--                                  made by postgres / service_role (privilege
--                                  escalation). No client path needs either.
--        TRUNCATE                — already removed by 01_PROD; repeated so this
--                                  file holds the full guarantee on its own.
--      A table-level REVOKE also removes column-level grants of the same
--      privileges, so column grants cannot leave a write path behind.
--   3. Re-states GRANT SELECT to anon, authenticated (no-op when present).
--   4. Verifies the result inside the transaction and aborts (nothing is
--      committed) if any client write privilege survives or SELECT is lost.
--
-- What it deliberately does NOT touch:
--   * The SECURITY DEFINER contribution RPC from migration 15: its body, owner,
--     EXECUTE grants.
--   * Table ownership, ENABLE / FORCE row level security, SELECT policies.
--   * The vector search RPCs, service_role, sequences, other tables.
--
-- Idempotent: safe to run more than once.
-- =============================================================================

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

-- 1. Permissive client write policies on the catalog.
DROP POLICY IF EXISTS "python_ekleme_izni" ON public.books;
DROP POLICY IF EXISTS "python_guncelleme_izni" ON public.books;

-- 2. Client write and DDL-adjacent privileges.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.books, public.book_embeddings
    FROM anon, authenticated, PUBLIC;

-- 3. Reads the app and AI/RAG depend on.
GRANT SELECT ON TABLE public.books, public.book_embeddings TO anon, authenticated;

-- 4. In-transaction verification (fail-closed: any failure rolls everything back).
DO $$
DECLARE
    v_role TEXT;
    v_table TEXT;
    v_priv TEXT;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        FOREACH v_table IN ARRAY ARRAY['public.books', 'public.book_embeddings'] LOOP
            IF NOT has_table_privilege(v_role, v_table, 'SELECT') THEN
                RAISE EXCEPTION '01c ABORTED: % lost SELECT on %', v_role, v_table;
            END IF;
            FOREACH v_priv IN ARRAY ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'] LOOP
                IF has_table_privilege(v_role, v_table, v_priv) THEN
                    RAISE EXCEPTION '01c ABORTED: % still holds % on % (inherited or granted by another grantor)',
                        v_role, v_priv, v_table;
                END IF;
            END LOOP;
            FOREACH v_priv IN ARRAY ARRAY['INSERT', 'UPDATE', 'REFERENCES'] LOOP
                IF has_any_column_privilege(v_role, v_table, v_priv) THEN
                    RAISE EXCEPTION '01c ABORTED: % still holds column-level % on %', v_role, v_priv, v_table;
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM pg_class c
        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
        WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
          AND a.grantee = 0
          AND a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    ) THEN
        RAISE EXCEPTION '01c ABORTED: PUBLIC still holds a write privilege on a catalog table';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'books'
          AND policyname IN ('python_ekleme_izni', 'python_guncelleme_izni')
    ) THEN
        RAISE EXCEPTION '01c ABORTED: a permissive books write policy is still present';
    END IF;

    RAISE NOTICE '01c OK: anon/authenticated/PUBLIC hold only SELECT on public.books and public.book_embeddings.';
END $$;

COMMIT;
