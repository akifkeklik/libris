-- RLS isolation for the notes and review tables (migrations 09, 10, 13), run as the real
-- `authenticated` role. Reader B must not see, change or delete reader A's rows, and must not
-- be able to write rows that claim to be A's. Throwaway database only (creates and deletes rows).
--
-- The CI stub auth.uid() returns one fixed id; here it reads a session setting so the test can
-- act as two different readers, the way Supabase derives it from the JWT.

CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('test.uid', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
$$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
END $$;
GRANT USAGE ON SCHEMA public, auth TO authenticated;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_notes, public.note_reviews,
      public.review_items, public.review_attempts TO authenticated;

INSERT INTO auth.users (id) VALUES ('aaaaaaaa-0000-0000-0000-00000000000a'), ('bbbbbbbb-0000-0000-0000-00000000000b')
ON CONFLICT DO NOTHING;

-- Reader A writes one row in every table.
SET ROLE authenticated;
SELECT set_config('test.uid', 'aaaaaaaa-0000-0000-0000-00000000000a', false);
INSERT INTO public.user_notes (id, user_id, book_id, note_type, content)
VALUES ('11111111-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-00000000000a', '978', 'key_takeaway', 'A private');
INSERT INTO public.note_reviews (note_id, user_id)
VALUES ('11111111-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-00000000000a');
INSERT INTO public.review_items (id, user_id, title, concept, question, answer, source_type)
VALUES ('22222222-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-00000000000a', 'T', 'C', 'Q?', 'A', 'key_takeaway');
INSERT INTO public.review_attempts (user_id, item_id, outcome, is_correct, stage_before, stage_after)
VALUES ('aaaaaaaa-0000-0000-0000-00000000000a', '22222222-0000-0000-0000-000000000002', 'remembered', true, 0, 1);

DO $$
DECLARE n INTEGER;
BEGIN
    SELECT count(*) INTO n FROM public.user_notes; IF n <> 1 THEN RAISE EXCEPTION 'A should see 1 own note, saw %', n; END IF;

    -- Reader B: sees nothing of A's.
    PERFORM set_config('test.uid', 'bbbbbbbb-0000-0000-0000-00000000000b', false);
    SELECT count(*) INTO n FROM public.user_notes;      IF n <> 0 THEN RAISE EXCEPTION 'B sees % of A''s notes', n; END IF;
    SELECT count(*) INTO n FROM public.note_reviews;    IF n <> 0 THEN RAISE EXCEPTION 'B sees % of A''s note reviews', n; END IF;
    SELECT count(*) INTO n FROM public.review_items;    IF n <> 0 THEN RAISE EXCEPTION 'B sees % of A''s review items', n; END IF;
    SELECT count(*) INTO n FROM public.review_attempts; IF n <> 0 THEN RAISE EXCEPTION 'B sees % of A''s attempts', n; END IF;

    -- B cannot change or delete A's rows (RLS filters them: 0 rows affected).
    UPDATE public.user_notes SET content = 'hijacked' WHERE id = '11111111-0000-0000-0000-000000000001';
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'B updated A''s note'; END IF;
    DELETE FROM public.review_items WHERE id = '22222222-0000-0000-0000-000000000002';
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'B deleted A''s review item'; END IF;

    -- B cannot write a row that claims to be A's.
    BEGIN
        INSERT INTO public.user_notes (user_id, book_id, note_type, content)
        VALUES ('aaaaaaaa-0000-0000-0000-00000000000a', '978', 'personal_note', 'forged');
        RAISE EXCEPTION 'B inserted a note as A';
    EXCEPTION WHEN insufficient_privilege THEN NULL;  -- 42501: new row violates row-level security policy
    END;

    -- A's data is intact.
    PERFORM set_config('test.uid', 'aaaaaaaa-0000-0000-0000-00000000000a', false);
    SELECT count(*) INTO n FROM public.user_notes WHERE content = 'A private'; IF n <> 1 THEN RAISE EXCEPTION 'A''s note changed'; END IF;
    SELECT count(*) INTO n FROM public.review_items; IF n <> 1 THEN RAISE EXCEPTION 'A''s review item lost'; END IF;
    RAISE NOTICE '>> test_09_10_13_rls_isolation: ALL CHECKS PASSED';
END $$;

RESET ROLE;
DELETE FROM auth.users WHERE id IN ('aaaaaaaa-0000-0000-0000-00000000000a', 'bbbbbbbb-0000-0000-0000-00000000000b');
