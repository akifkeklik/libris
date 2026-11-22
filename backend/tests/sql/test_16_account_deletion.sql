-- Runtime checks for migration 16 (delete_my_account). Run after all migrations in CI.
-- The CI stub's auth.uid() returns 00000000-0000-0000-0000-000000000000.
DO $$
DECLARE
    me    CONSTANT UUID := '00000000-0000-0000-0000-000000000000';
    other CONSTANT UUID := '11111111-1111-1111-1111-111111111111';
    n     INTEGER;
    t     TEXT;
BEGIN
    INSERT INTO auth.users (id) VALUES (me), (other) ON CONFLICT DO NOTHING;
    INSERT INTO public.books (isbn13, title) VALUES ('9780000016001', 'Deletion Test Book') ON CONFLICT DO NOTHING;

    -- 1. Every FK to auth.users cascades after migration 16.
    SELECT count(*) INTO n FROM pg_constraint
    WHERE contype = 'f' AND confrelid = 'auth.users'::regclass
      AND connamespace = 'public'::regnamespace AND confdeltype <> 'c';
    IF n <> 0 THEN RAISE EXCEPTION '% FK(s) to auth.users do not cascade', n; END IF;

    -- 2. Data of both users in every user table that exists here (a trigger may already copy
    --    favorites into user_interactions, hence ON CONFLICT DO NOTHING there).
    INSERT INTO public.favorites (user_id, book_id) VALUES (me, '9780000016001'), (other, '9780000016001');
    UPDATE public.books SET added_by = me WHERE isbn13 = '9780000016001';
    IF to_regclass('public.user_interactions') IS NOT NULL THEN
        EXECUTE 'INSERT INTO public.user_interactions (user_id, book_id, interaction_type) VALUES ($1, $3, ''like''), ($2, $3, ''like'') ON CONFLICT DO NOTHING'
            USING me, other, '9780000016001';
    END IF;
    IF to_regclass('public.user_notes') IS NOT NULL THEN
        EXECUTE 'INSERT INTO public.user_notes (user_id, book_id, note_type, content) VALUES ($1, $3, ''personal_note'', ''mine''), ($2, $3, ''personal_note'', ''theirs'')'
            USING me, other, '9780000016001';
    END IF;

    -- 3. Delete the caller.
    PERFORM public.delete_my_account();

    IF EXISTS (SELECT 1 FROM auth.users WHERE id = me) THEN RAISE EXCEPTION 'caller still in auth.users'; END IF;
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = other) THEN RAISE EXCEPTION 'another user was deleted'; END IF;

    -- 4. No row of the caller survives in any public table with a user_id column.
    FOR t IN SELECT table_name FROM information_schema.columns
             WHERE table_schema = 'public' AND column_name = 'user_id' LOOP
        EXECUTE format('SELECT count(*) FROM public.%I WHERE user_id = $1', t) INTO n USING me;
        IF n <> 0 THEN RAISE EXCEPTION '% row(s) of the deleted user left in %', n, t; END IF;
    END LOOP;
    SELECT count(*) INTO n FROM public.favorites WHERE user_id = other;
    IF n <> 1 THEN RAISE EXCEPTION 'the other user lost data (favorites=%)', n; END IF;

    -- 5. The contributed book stays in the catalog, without the link to the person.
    IF NOT EXISTS (SELECT 1 FROM public.books WHERE isbn13 = '9780000016001' AND added_by IS NULL) THEN
        RAISE EXCEPTION 'book removed or still attributed to the deleted user';
    END IF;

    -- cleanup
    DELETE FROM public.favorites WHERE user_id = other;
    DELETE FROM auth.users WHERE id = other;
    DELETE FROM public.books WHERE isbn13 = '9780000016001';
    RAISE NOTICE '>> test_16_account_deletion: ALL CHECKS PASSED';
END $$;
