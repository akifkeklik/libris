-- Runtime checks for migration 19 (import approval queue). Throwaway database only.

CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('test.uid', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
$$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
END $$;
GRANT USAGE ON SCHEMA public, auth TO authenticated, anon;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated, anon;
\ir ../../scripts/19_import_queue.sql
\ir ../../scripts/19_import_queue.sql

INSERT INTO auth.users (id) VALUES ('a2000000-0000-0000-0000-00000000000a'), ('b2000000-0000-0000-0000-00000000000b')
ON CONFLICT DO NOTHING;

SET ROLE authenticated;
SELECT set_config('test.uid', 'a2000000-0000-0000-0000-00000000000a', false);
DO $$ DECLARE n INTEGER; BEGIN
    INSERT INTO public.import_items (source, kind, content_hash, book_title, content)
    VALUES ('kindle', 'highlight', repeat('a', 64), 'Atomic Habits', 'Habits compound.');
    -- Same hash again (re-import): ignored with ON CONFLICT, rejected without it.
    INSERT INTO public.import_items (source, kind, content_hash, book_title, content)
    VALUES ('readwise', 'highlight', repeat('a', 64), 'Atomic Habits', 'Habits compound.')
    ON CONFLICT (user_id, content_hash) DO NOTHING;
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'duplicate hash inserted'; END IF;
    -- Shape: a shelf needs a shelf and no text; a highlight needs text.
    BEGIN
        INSERT INTO public.import_items (source, kind, content_hash, book_title) VALUES ('goodreads', 'shelf', repeat('b', 64), 'X');
        RAISE EXCEPTION 'shelf without shelf accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO public.import_items (source, kind, content_hash, book_title, content) VALUES ('kindle', 'highlight', repeat('c', 64), 'X', '   ');
        RAISE EXCEPTION 'blank highlight accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO public.import_items (source, kind, content_hash, book_title, content) VALUES ('kindle', 'highlight', 'not-a-hash', 'X', 'y');
        RAISE EXCEPTION 'bad hash accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    -- Writing for another reader is refused.
    BEGIN
        INSERT INTO public.import_items (user_id, source, kind, content_hash, book_title, content)
        VALUES ('b2000000-0000-0000-0000-00000000000b', 'kindle', 'highlight', repeat('d', 64), 'X', 'y');
        RAISE EXCEPTION 'a wrote into b''s queue';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;

-- b cannot see or change a's queue.
INSERT INTO public.import_items (user_id, source, kind, content_hash, book_title, content)
VALUES ('b2000000-0000-0000-0000-00000000000b', 'kindle', 'highlight', repeat('e', 64), 'Dune', 'Fear is the mind-killer.');
SET ROLE authenticated;
SELECT set_config('test.uid', 'b2000000-0000-0000-0000-00000000000b', false);
DO $$ DECLARE n INTEGER; BEGIN
    SELECT count(*) INTO n FROM public.import_items; IF n <> 1 THEN RAISE EXCEPTION 'b sees % rows', n; END IF;
    UPDATE public.import_items SET status = 'approved' WHERE content_hash = repeat('a', 64);
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'b approved a''s entry'; END IF;
END $$;
RESET ROLE;

-- The pending cap (5000) holds even for direct inserts; rejected/approved rows do not count.
DO $$ BEGIN
    INSERT INTO public.import_items (user_id, source, kind, content_hash, book_title, content, status)
    SELECT 'b2000000-0000-0000-0000-00000000000b', 'kindle', 'highlight', md5(g::text) || md5((g + 1)::text), 'Bulk', 'x', 'pending'
    FROM generate_series(1, 4999) g;
    BEGIN
        INSERT INTO public.import_items (user_id, source, kind, content_hash, book_title, content)
        VALUES ('b2000000-0000-0000-0000-00000000000b', 'kindle', 'highlight', repeat('f', 64), 'Bulk', 'one too many');
        RAISE EXCEPTION 'cap not enforced';
    EXCEPTION WHEN program_limit_exceeded THEN NULL; END;
    INSERT INTO public.import_items (user_id, source, kind, content_hash, book_title, content, status)
    VALUES ('b2000000-0000-0000-0000-00000000000b', 'kindle', 'highlight', repeat('f', 64), 'Bulk', 'decided', 'rejected');
END $$;

-- anon: nothing. Account deletion cascades.
SET ROLE anon;
DO $$ BEGIN
    BEGIN PERFORM 1 FROM public.import_items; RAISE EXCEPTION 'anon read the queue';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;
DELETE FROM auth.users WHERE id IN ('a2000000-0000-0000-0000-00000000000a', 'b2000000-0000-0000-0000-00000000000b');
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.import_items WHERE user_id IN ('a2000000-0000-0000-0000-00000000000a', 'b2000000-0000-0000-0000-00000000000b')) THEN
        RAISE EXCEPTION 'queue survived account deletion';
    END IF;
    RAISE NOTICE '>> test_19_import_queue: ALL CHECKS PASSED';
END $$;
