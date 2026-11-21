-- =============================================================================
-- TEST: 01c CATALOG WRITE LOCKDOWN — RUNTIME (SET ROLE) VERIFICATION
-- =============================================================================
-- File: backend/scripts/hardening/test_01c_catalog_write_lockdown_runtime.sql
--
-- Scope: public.books and public.book_embeddings only.
--   0. Recreate the production drift: Supabase default table grants (incl.
--      REFERENCES, TRIGGER), a column-level UPDATE grant, a PUBLIC grant, and the
--      two permissive policies "python_ekleme_izni" (INSERT WITH CHECK true) and
--      "python_guncelleme_izni" (UPDATE USING true).
--   1. Prove the hole is real: anon can INSERT and UPDATE books.
--   2. Apply 01c_DRAFT_catalog_write_lockdown.sql twice (idempotency): the second run must
--      succeed and leave table/column ACLs, policies, owner and RLS flags identical to the
--      snapshot taken after the first run.
--   3. anon / authenticated: INSERT, UPDATE, DELETE on books and book_embeddings
--      are denied; no TRUNCATE / REFERENCES / TRIGGER / column-level / PUBLIC
--      write privilege survives; SELECT is kept.
--   4. Reads the app and AI/RAG need still work: SELECT books, SELECT
--      book_embeddings, match_query_embeddings, match_book_embeddings (anon).
--   5. Reader contributions still work: authenticated add_catalog_book inserts,
--      never overwrites; anon cannot execute it.
--   6. Catalog invariant production depends on: add_catalog_book's owner owns
--      public.books (or has BYPASSRLS) and books is not FORCE ROW LEVEL SECURITY,
--      so the SECURITY DEFINER insert keeps working with no INSERT policy.
--   7. Rollback restores the grants but neither TRUNCATE nor the permissive
--      policies: clients still cannot write a catalog row.
--   8. Re-apply 01c (forward after rollback). CI then runs the read-only
--      verify_01c_catalog_write_lockdown.sql against the final state.
--
-- Run (CI, throwaway database, from the repository root, after all migrations):
--   psql -v ON_ERROR_STOP=1 -f backend/scripts/hardening/test_01c_catalog_write_lockdown_runtime.sql
-- NEVER run against production: it applies 01c and its rollback, and creates/deletes test rows.
-- =============================================================================

\set ON_ERROR_STOP on

-- ─── 0. Setup: roles, Supabase-style default grants, production policy drift ──
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role; END IF;
END $$;

-- CI creates the API roles after the numbered migrations ran, so migration 15's role-guarded
-- GRANT EXECUTE was skipped. Re-apply it (idempotent) to get production's function grants.
\i backend/scripts/15_reader_catalog_contributions.sql

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT USAGE ON SCHEMA auth TO anon, authenticated;
-- Supabase grants table DML to the API roles by default and relies on RLS.
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER ON public.books, public.book_embeddings TO anon, authenticated;
-- Extra drift 01c must also clean up: a column-level grant and a PUBLIC grant.
GRANT UPDATE (title) ON public.books TO authenticated;
GRANT INSERT ON public.book_embeddings TO PUBLIC;

ALTER TABLE public.books ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.book_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "python_ekleme_izni" ON public.books;
DROP POLICY IF EXISTS "python_guncelleme_izni" ON public.books;
CREATE POLICY "python_ekleme_izni" ON public.books FOR INSERT WITH CHECK (true);
CREATE POLICY "python_guncelleme_izni" ON public.books FOR UPDATE USING (true) WITH CHECK (true);

-- Fixture rows (as the owner): one catalog book with an embedding for the RPCs.
DELETE FROM public.books WHERE isbn13 IN ('9790000001017', '9790000001024', '9790000001031', '9790000001048');
INSERT INTO public.books (isbn13, title, authors, categories, description)
VALUES ('9790000001017', 'Lockdown Fixture', 'Fixture Author', 'Test', 'fixture');
INSERT INTO public.book_embeddings (book_id, embedding, content_hash, model_version)
VALUES ('9790000001017', array_fill(0.01::real, ARRAY[3072])::vector(3072), 'fixture-hash', 'fixture-model');

-- ─── 1. The hole is real before 01c ───────────────────────────────────────────
DO $$
DECLARE
    v_title TEXT;
BEGIN
    SET ROLE anon;
    INSERT INTO public.books (isbn13, title, authors) VALUES ('9790000001024', 'Anon Insert', 'Anon');
    UPDATE public.books SET title = 'Vandalised' WHERE isbn13 = '9790000001017';
    RESET ROLE;

    SELECT title INTO v_title FROM public.books WHERE isbn13 = '9790000001017';
    IF v_title <> 'Vandalised' OR NOT EXISTS (SELECT 1 FROM public.books WHERE isbn13 = '9790000001024') THEN
        RAISE EXCEPTION 'PRECONDITION FAILED: drift setup did not reproduce the anon write hole';
    END IF;

    -- Restore fixtures as the owner.
    DELETE FROM public.books WHERE isbn13 = '9790000001024';
    UPDATE public.books SET title = 'Lockdown Fixture' WHERE isbn13 = '9790000001017';
    RAISE NOTICE '>> STEP 1 OK: anon could INSERT/UPDATE books before 01c (hole reproduced).';
END $$;

-- ─── 2. Apply the candidate migration (twice: must be idempotent) ─────────────
\i backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown.sql

-- Snapshot of everything 01c controls, taken after the FIRST application: table ACLs,
-- column ACLs, policies, owner and RLS flags of both catalog tables.
DROP TABLE IF EXISTS pg_temp.t01c_after_first_apply;
CREATE TEMP TABLE t01c_after_first_apply AS
SELECT 'table_acl' AS kind,
       c.relname || '|' || CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
       || '|' || a.privilege_type || '|' || pg_get_userbyid(a.grantor) || '|' || a.is_grantable AS item
FROM pg_class c
CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
UNION ALL
SELECT 'column_acl',
       c.relname || '.' || att.attname || '|' || CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
       || '|' || a.privilege_type
FROM pg_class c
JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum > 0 AND NOT att.attisdropped AND att.attacl IS NOT NULL
CROSS JOIN LATERAL aclexplode(att.attacl) a
WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
UNION ALL
SELECT 'policy',
       p.tablename || '|' || p.policyname || '|' || p.cmd || '|' || p.permissive || '|' || p.roles::text
       || '|' || coalesce(p.qual, '') || '|' || coalesce(p.with_check, '')
FROM pg_policies p
WHERE p.schemaname = 'public' AND p.tablename IN ('books', 'book_embeddings')
UNION ALL
SELECT 'relation',
       c.relname || '|' || pg_get_userbyid(c.relowner) || '|' || c.relrowsecurity || '|' || c.relforcerowsecurity
FROM pg_class c
WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass);

-- Second application. ON_ERROR_STOP aborts the test if it fails; its own in-transaction
-- check must pass again on the already-locked-down state.
\i backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown.sql

DO $$
DECLARE
    v_first INTEGER;
    v_missing INTEGER;
    v_added INTEGER;
BEGIN
    SELECT count(*) INTO v_first FROM pg_temp.t01c_after_first_apply;
    IF v_first = 0
       OR NOT EXISTS (SELECT 1 FROM pg_temp.t01c_after_first_apply WHERE kind = 'table_acl' AND item LIKE 'books|anon|SELECT|%')
       OR NOT EXISTS (SELECT 1 FROM pg_temp.t01c_after_first_apply WHERE kind = 'table_acl' AND item LIKE 'book_embeddings|authenticated|SELECT|%') THEN
        RAISE EXCEPTION 'FAILED: STEP 2 snapshot after the first 01c application is empty or lost SELECT';
    END IF;

    WITH now_state AS (
        SELECT 'table_acl' AS kind,
               c.relname || '|' || CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
               || '|' || a.privilege_type || '|' || pg_get_userbyid(a.grantor) || '|' || a.is_grantable AS item
        FROM pg_class c
        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
        WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
        UNION ALL
        SELECT 'column_acl',
               c.relname || '.' || att.attname || '|' || CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END
               || '|' || a.privilege_type
        FROM pg_class c
        JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum > 0 AND NOT att.attisdropped AND att.attacl IS NOT NULL
        CROSS JOIN LATERAL aclexplode(att.attacl) a
        WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
        UNION ALL
        SELECT 'policy',
               p.tablename || '|' || p.policyname || '|' || p.cmd || '|' || p.permissive || '|' || p.roles::text
               || '|' || coalesce(p.qual, '') || '|' || coalesce(p.with_check, '')
        FROM pg_policies p
        WHERE p.schemaname = 'public' AND p.tablename IN ('books', 'book_embeddings')
        UNION ALL
        SELECT 'relation',
               c.relname || '|' || pg_get_userbyid(c.relowner) || '|' || c.relrowsecurity || '|' || c.relforcerowsecurity
        FROM pg_class c
        WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
    )
    SELECT (SELECT count(*) FROM (SELECT kind, item FROM pg_temp.t01c_after_first_apply EXCEPT SELECT kind, item FROM now_state) m),
           (SELECT count(*) FROM (SELECT kind, item FROM now_state EXCEPT SELECT kind, item FROM pg_temp.t01c_after_first_apply) n)
    INTO v_missing, v_added;

    IF v_missing <> 0 OR v_added <> 0 THEN
        RAISE EXCEPTION 'FAILED: second 01c application changed the catalog security state (% entries removed, % added)',
            v_missing, v_added;
    END IF;

    DROP TABLE pg_temp.t01c_after_first_apply;
    RAISE NOTICE '>> STEP 2 OK: 01c applied twice; second run committed and left all % ACL/policy/owner/RLS entries unchanged.', v_first;
END $$;

-- ─── 3. Client writes on both catalog tables are denied ───────────────────────
DO $$
DECLARE
    r TEXT;
    v_title TEXT;
    v_rows INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename IN ('books', 'book_embeddings') AND cmd <> 'SELECT'
    ) THEN
        RAISE EXCEPTION 'FAILED: a non-SELECT policy is still present on books/book_embeddings';
    END IF;

    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF has_table_privilege(r, 'public.books', 'INSERT')
           OR has_table_privilege(r, 'public.books', 'UPDATE')
           OR has_table_privilege(r, 'public.books', 'DELETE')
           OR has_table_privilege(r, 'public.books', 'TRUNCATE')
           OR has_table_privilege(r, 'public.book_embeddings', 'INSERT')
           OR has_table_privilege(r, 'public.book_embeddings', 'UPDATE')
           OR has_table_privilege(r, 'public.book_embeddings', 'DELETE')
           OR has_table_privilege(r, 'public.book_embeddings', 'TRUNCATE')
           OR has_table_privilege(r, 'public.books', 'REFERENCES')
           OR has_table_privilege(r, 'public.books', 'TRIGGER')
           OR has_table_privilege(r, 'public.book_embeddings', 'REFERENCES')
           OR has_table_privilege(r, 'public.book_embeddings', 'TRIGGER')
           OR has_any_column_privilege(r, 'public.books', 'INSERT')
           OR has_any_column_privilege(r, 'public.books', 'UPDATE')
           OR has_any_column_privilege(r, 'public.book_embeddings', 'INSERT')
           OR has_any_column_privilege(r, 'public.book_embeddings', 'UPDATE') THEN
            RAISE EXCEPTION 'FAILED: role % still holds a write privilege on a catalog table', r;
        END IF;
        IF NOT has_table_privilege(r, 'public.books', 'SELECT')
           OR NOT has_table_privilege(r, 'public.book_embeddings', 'SELECT') THEN
            RAISE EXCEPTION 'FAILED: role % lost SELECT on a catalog table', r;
        END IF;

        EXECUTE format('SET ROLE %I', r);
        PERFORM set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', false);

        BEGIN
            INSERT INTO public.books (isbn13, title, authors) VALUES ('9790000001031', 'Denied', 'X');
            RAISE EXCEPTION 'FAILED: % could INSERT into books', r;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;

        BEGIN
            UPDATE public.books SET title = 'Denied' WHERE isbn13 = '9790000001017';
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            IF v_rows <> 0 THEN RAISE EXCEPTION 'FAILED: % could UPDATE books', r; END IF;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;

        BEGIN
            DELETE FROM public.books WHERE isbn13 = '9790000001017';
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            IF v_rows <> 0 THEN RAISE EXCEPTION 'FAILED: % could DELETE from books', r; END IF;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;

        BEGIN
            INSERT INTO public.book_embeddings (book_id, embedding, content_hash, model_version)
            VALUES ('9790000001017', array_fill(0.5::real, ARRAY[3072])::vector(3072), 'poison', 'poison');
            RAISE EXCEPTION 'FAILED: % could INSERT into book_embeddings', r;
        EXCEPTION WHEN insufficient_privilege OR unique_violation THEN
            -- unique_violation would mean the INSERT got past privileges and RLS: treat as failure.
            IF SQLSTATE = '23505' THEN RAISE EXCEPTION 'FAILED: % passed the book_embeddings write checks', r; END IF;
        END;

        BEGIN
            UPDATE public.book_embeddings SET content_hash = 'poison' WHERE book_id = '9790000001017';
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            IF v_rows <> 0 THEN RAISE EXCEPTION 'FAILED: % could UPDATE book_embeddings', r; END IF;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;

        BEGIN
            DELETE FROM public.book_embeddings WHERE book_id = '9790000001017';
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            IF v_rows <> 0 THEN RAISE EXCEPTION 'FAILED: % could DELETE from book_embeddings', r; END IF;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;

        RESET ROLE;
    END LOOP;

    SELECT title INTO v_title FROM public.books WHERE isbn13 = '9790000001017';
    IF v_title IS DISTINCT FROM 'Lockdown Fixture' THEN RAISE EXCEPTION 'FAILED: fixture book was modified'; END IF;
    IF NOT EXISTS (SELECT 1 FROM public.book_embeddings WHERE book_id = '9790000001017' AND content_hash = 'fixture-hash') THEN
        RAISE EXCEPTION 'FAILED: fixture embedding was modified';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class c
        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a
        WHERE c.oid IN ('public.books'::regclass, 'public.book_embeddings'::regclass)
          AND a.grantee = 0 AND a.privilege_type <> 'SELECT'
    ) THEN
        RAISE EXCEPTION 'FAILED: PUBLIC still holds a write privilege on a catalog table';
    END IF;
    RAISE NOTICE '>> STEP 3 OK: anon/authenticated/PUBLIC cannot write books or book_embeddings.';
END $$;

-- ─── 4. Read paths for the catalog and AI/RAG still work ──────────────────────
DO $$
DECLARE
    r TEXT;
    n INTEGER;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        EXECUTE format('SET ROLE %I', r);

        SELECT count(*) INTO n FROM public.books WHERE isbn13 = '9790000001017';
        IF n <> 1 THEN RAISE EXCEPTION 'FAILED: % cannot read books', r; END IF;

        SELECT count(*) INTO n FROM public.book_embeddings WHERE book_id = '9790000001017';
        IF n <> 1 THEN RAISE EXCEPTION 'FAILED: % cannot read book_embeddings (SECURITY INVOKER RPCs need it)', r; END IF;

        SELECT count(*) INTO n
        FROM public.match_query_embeddings(array_fill(0.01::real, ARRAY[3072])::vector(3072), 0.0, 5)
        WHERE book_id = '9790000001017';
        IF n <> 1 THEN RAISE EXCEPTION 'FAILED: % match_query_embeddings (RAG) returned no fixture row', r; END IF;

        PERFORM * FROM public.match_book_embeddings(ARRAY['9790000001017'], 0.0, 5);

        RESET ROLE;
    END LOOP;
    RAISE NOTICE '>> STEP 4 OK: books, book_embeddings and both vector RPCs readable by anon/authenticated.';
END $$;

-- ─── 5. Reader contributions keep working through the definer RPC ─────────────
DO $$
DECLARE
    ok BOOLEAN;
    v_added_by UUID;
    v_title TEXT;
BEGIN
    SET ROLE anon;
    BEGIN
        PERFORM public.add_catalog_book('9790000001048', 'Anon Book', 'Anon', '', '', '', 0, '');
        RAISE EXCEPTION 'FAILED: anon could execute add_catalog_book';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    RESET ROLE;

    SET ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', false);
    ok := public.add_catalog_book('9790000001048', 'Reader Book', 'Reader', 'Science', '', '', 10, '2024');
    IF ok IS NOT TRUE THEN RAISE EXCEPTION 'FAILED: authenticated add_catalog_book did not insert'; END IF;
    ok := public.add_catalog_book('9790000001017', 'Overwrite Attempt', 'Attacker', '', '', '', 0, '');
    IF ok IS NOT FALSE THEN RAISE EXCEPTION 'FAILED: add_catalog_book reported an overwrite'; END IF;
    RESET ROLE;

    SELECT added_by INTO v_added_by FROM public.books WHERE isbn13 = '9790000001048';
    IF v_added_by IS NULL THEN RAISE EXCEPTION 'FAILED: contributed book has no added_by'; END IF;
    SELECT title INTO v_title FROM public.books WHERE isbn13 = '9790000001017';
    IF v_title <> 'Lockdown Fixture' THEN RAISE EXCEPTION 'FAILED: add_catalog_book overwrote an existing row'; END IF;
    RAISE NOTICE '>> STEP 5 OK: add_catalog_book works for authenticated, denied for anon, never overwrites.';
END $$;

-- ─── 6. Ownership invariant the definer insert relies on in production ────────
DO $$
DECLARE
    v_table_owner OID;
    v_forced BOOLEAN;
    v_fn_owner OID;
BEGIN
    SELECT relowner, relforcerowsecurity INTO v_table_owner, v_forced
    FROM pg_class WHERE oid = 'public.books'::regclass;
    SELECT proowner INTO v_fn_owner
    FROM pg_proc WHERE oid = 'public.add_catalog_book(text,text,text,text,text,text,integer,text)'::regprocedure;

    IF v_forced THEN
        RAISE EXCEPTION 'FAILED: public.books has FORCE ROW LEVEL SECURITY; add_catalog_book would need an INSERT policy';
    END IF;
    IF v_fn_owner <> v_table_owner
       AND NOT (SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE oid = v_fn_owner) THEN
        RAISE EXCEPTION 'FAILED: add_catalog_book owner neither owns public.books nor bypasses RLS';
    END IF;
    RAISE NOTICE '>> STEP 6 OK: add_catalog_book owner can insert into books without a client INSERT policy.';
END $$;

-- ─── 7. Rollback: grants back, hole stays closed ──────────────────────────────
\i backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown_rollback.sql

DO $$
DECLARE
    r TEXT;
    v_rows INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'books'
          AND policyname IN ('python_ekleme_izni', 'python_guncelleme_izni')
    ) THEN
        RAISE EXCEPTION 'FAILED: rollback re-created a permissive books write policy';
    END IF;

    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF NOT has_table_privilege(r, 'public.books', 'INSERT')
           OR NOT has_table_privilege(r, 'public.book_embeddings', 'UPDATE') THEN
            RAISE EXCEPTION 'FAILED: rollback did not restore the table grants for %', r;
        END IF;
        IF has_table_privilege(r, 'public.books', 'TRUNCATE')
           OR has_table_privilege(r, 'public.book_embeddings', 'TRUNCATE') THEN
            RAISE EXCEPTION 'FAILED: rollback gave TRUNCATE back to %', r;
        END IF;

        EXECUTE format('SET ROLE %I', r);
        BEGIN
            INSERT INTO public.books (isbn13, title, authors) VALUES ('9790000001031', 'After Rollback', 'X');
            RAISE EXCEPTION 'FAILED: % could INSERT into books after rollback', r;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
        UPDATE public.books SET title = 'After Rollback' WHERE isbn13 = '9790000001017';
        GET DIAGNOSTICS v_rows = ROW_COUNT;
        IF v_rows <> 0 THEN RAISE EXCEPTION 'FAILED: % could UPDATE books after rollback', r; END IF;
        RESET ROLE;
    END LOOP;
    RAISE NOTICE '>> STEP 7 OK: rollback restored grants only; RLS still blocks client catalog writes.';
END $$;

-- ─── 8. Forward again after rollback ──────────────────────────────────────────
\i backend/scripts/hardening/01c_DRAFT_catalog_write_lockdown.sql

DO $$
BEGIN
    IF has_table_privilege('anon', 'public.books', 'INSERT')
       OR has_table_privilege('authenticated', 'public.book_embeddings', 'UPDATE')
       OR NOT has_table_privilege('anon', 'public.book_embeddings', 'SELECT') THEN
        RAISE EXCEPTION 'FAILED: re-forward after rollback did not restore the lockdown';
    END IF;
    RAISE NOTICE '>> STEP 8 OK: 01c re-applied cleanly after rollback.';
END $$;

-- ─── Cleanup (as owner) ───────────────────────────────────────────────────────
RESET ROLE;
RESET request.jwt.claim.sub;
DELETE FROM public.books WHERE isbn13 IN ('9790000001017', '9790000001024', '9790000001031', '9790000001048');
\echo '>> test_01c_catalog_write_lockdown_runtime: ALL CHECKS PASSED'
