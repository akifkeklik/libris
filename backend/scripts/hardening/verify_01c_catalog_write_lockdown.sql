-- =============================================================================
-- VERIFY 01c: CATALOG WRITE LOCKDOWN (READ-ONLY)
-- =============================================================================
-- File: backend/scripts/hardening/verify_01c_catalog_write_lockdown.sql
--
-- Run after 01c_DRAFT_catalog_write_lockdown.sql. Every statement is a catalog
-- read inside a READ ONLY transaction that is rolled back; it changes nothing
-- and is safe to run in the Supabase SQL Editor (postgres role).
--
-- Output: one row per check (check_name | expected | actual | status), ending
-- with an OVERALL row. status is PASS, FAIL or WARN.
--   FAIL = the lockdown or an invariant it depends on is broken.
--   WARN = an extra non-SELECT policy exists; it is inert while the client
--          write grants are revoked, but should be reviewed and dropped.
--
-- CI runs it with: psql -At -F '|' -f ... and fails on any '|FAIL' row.
-- =============================================================================

BEGIN READ ONLY;

WITH
roles(role_name) AS (VALUES ('anon'), ('authenticated')),
tbls(table_name) AS (VALUES ('public.books'), ('public.book_embeddings')),
write_privs(priv) AS (VALUES ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')),
col_privs(priv) AS (VALUES ('INSERT'), ('UPDATE'), ('REFERENCES')),
fn AS (
    SELECT p.oid, p.proowner, p.prosecdef
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'add_catalog_book'
),
vec_fn AS (
    SELECT p.oid, p.prosecdef
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'match_query_embeddings'
),
checks(ord, check_name, expected, actual, status) AS (
    -- 1. Reads kept.
    SELECT 10, r.role_name || ' SELECT ' || t.table_name, 'true',
           has_table_privilege(r.role_name, t.table_name, 'SELECT')::text,
           CASE WHEN has_table_privilege(r.role_name, t.table_name, 'SELECT') THEN 'PASS' ELSE 'FAIL' END
    FROM roles r CROSS JOIN tbls t

    -- 2. Table-level writes / DDL-adjacent privileges removed (includes inherited).
    UNION ALL
    SELECT 20, r.role_name || ' ' || w.priv || ' ' || t.table_name, 'false',
           has_table_privilege(r.role_name, t.table_name, w.priv)::text,
           CASE WHEN has_table_privilege(r.role_name, t.table_name, w.priv) THEN 'FAIL' ELSE 'PASS' END
    FROM roles r CROSS JOIN tbls t CROSS JOIN write_privs w

    -- 3. No column-level write grant left behind.
    UNION ALL
    SELECT 30, r.role_name || ' column ' || c.priv || ' ' || t.table_name, 'false',
           has_any_column_privilege(r.role_name, t.table_name, c.priv)::text,
           CASE WHEN has_any_column_privilege(r.role_name, t.table_name, c.priv) THEN 'FAIL' ELSE 'PASS' END
    FROM roles r CROSS JOIN tbls t CROSS JOIN col_privs c

    -- 4. PUBLIC holds no write privilege.
    UNION ALL
    SELECT 40, 'PUBLIC write privileges on ' || t.table_name, '0',
           count(a.privilege_type)::text,
           CASE WHEN count(a.privilege_type) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM tbls t
    JOIN pg_class c ON c.oid = t.table_name::regclass
    LEFT JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
           ON a.grantee = 0
          AND a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    GROUP BY t.table_name

    -- 5. Policies: permissive write policies gone, SELECT policies present, extras flagged.
    UNION ALL
    SELECT 50, 'books permissive write policies (python_*)', '0', count(*)::text,
           CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'books'
      AND policyname IN ('python_ekleme_izni', 'python_guncelleme_izni')
    UNION ALL
    SELECT 51, 'other non-SELECT policies on ' || t.table_name, '0', count(p.policyname)::text,
           CASE WHEN count(p.policyname) = 0 THEN 'PASS' ELSE 'WARN' END
    FROM tbls t
    LEFT JOIN pg_policies p
           ON p.schemaname = 'public' AND p.tablename = split_part(t.table_name, '.', 2) AND p.cmd <> 'SELECT'
    GROUP BY t.table_name
    UNION ALL
    SELECT 52, 'SELECT/ALL policy present on ' || t.table_name, '>=1', count(p.policyname)::text,
           CASE WHEN count(p.policyname) >= 1 THEN 'PASS' ELSE 'FAIL' END
    FROM tbls t
    LEFT JOIN pg_policies p
           ON p.schemaname = 'public' AND p.tablename = split_part(t.table_name, '.', 2) AND p.cmd IN ('SELECT', 'ALL')
    GROUP BY t.table_name

    -- 6. Invariants 01c must not have changed (owner, RLS mode, definer RPC, invoker RPC).
    UNION ALL
    SELECT 60, 'RLS enabled on ' || t.table_name, 'true', c.relrowsecurity::text,
           CASE WHEN c.relrowsecurity THEN 'PASS' ELSE 'FAIL' END
    FROM tbls t JOIN pg_class c ON c.oid = t.table_name::regclass
    UNION ALL
    SELECT 61, 'public.books relforcerowsecurity', 'false', c.relforcerowsecurity::text,
           CASE WHEN c.relforcerowsecurity THEN 'FAIL' ELSE 'PASS' END
    FROM pg_class c WHERE c.oid = 'public.books'::regclass
    UNION ALL
    SELECT 62, 'add_catalog_book exists', '1', count(*)::text,
           CASE WHEN count(*) = 1 THEN 'PASS' ELSE 'FAIL' END
    FROM fn
    UNION ALL
    SELECT 63, 'add_catalog_book SECURITY DEFINER', 'true', fn.prosecdef::text,
           CASE WHEN fn.prosecdef THEN 'PASS' ELSE 'FAIL' END
    FROM fn
    UNION ALL
    SELECT 64, 'add_catalog_book owner can insert into books (owns it or BYPASSRLS)', 'true',
           (fn.proowner = c.relowner OR r.rolbypassrls OR r.rolsuper)::text,
           CASE WHEN fn.proowner = c.relowner OR r.rolbypassrls OR r.rolsuper THEN 'PASS' ELSE 'FAIL' END
    FROM fn
    JOIN pg_roles r ON r.oid = fn.proowner
    JOIN pg_class c ON c.oid = 'public.books'::regclass
    UNION ALL
    SELECT 65, 'authenticated EXECUTE add_catalog_book', 'true',
           has_function_privilege('authenticated', fn.oid, 'EXECUTE')::text,
           CASE WHEN has_function_privilege('authenticated', fn.oid, 'EXECUTE') THEN 'PASS' ELSE 'FAIL' END
    FROM fn
    UNION ALL
    SELECT 66, 'anon EXECUTE add_catalog_book', 'false',
           has_function_privilege('anon', fn.oid, 'EXECUTE')::text,
           CASE WHEN has_function_privilege('anon', fn.oid, 'EXECUTE') THEN 'FAIL' ELSE 'PASS' END
    FROM fn
    UNION ALL
    SELECT 67, 'match_query_embeddings SECURITY INVOKER', 'true', (NOT bool_or(v.prosecdef))::text,
           CASE WHEN count(*) >= 1 AND NOT bool_or(v.prosecdef) THEN 'PASS' ELSE 'FAIL' END
    FROM vec_fn v
    UNION ALL
    SELECT 68, r.role_name || ' EXECUTE match_query_embeddings', 'true',
           bool_and(has_function_privilege(r.role_name, v.oid, 'EXECUTE'))::text,
           CASE WHEN bool_and(has_function_privilege(r.role_name, v.oid, 'EXECUTE')) THEN 'PASS' ELSE 'FAIL' END
    FROM roles r CROSS JOIN vec_fn v
    GROUP BY r.role_name
)
SELECT check_name, expected, actual, status
FROM (
    SELECT ord, check_name, expected, actual, status FROM checks
    UNION ALL
    SELECT 999, 'OVERALL',
           'no FAIL',
           count(*) FILTER (WHERE status = 'FAIL') || ' FAIL / '
               || count(*) FILTER (WHERE status = 'WARN') || ' WARN / '
               || count(*) || ' checks',
           CASE WHEN count(*) FILTER (WHERE status = 'FAIL') = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM checks
) s
ORDER BY ord, check_name;

ROLLBACK;
