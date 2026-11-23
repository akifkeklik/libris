-- Runtime checks for migration 20 (learning settings). Throwaway database only.
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('test.uid', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
$$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
END $$;
GRANT USAGE ON SCHEMA public, auth TO authenticated, anon;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated, anon;
\ir ../../scripts/20_learning_settings.sql
\ir ../../scripts/20_learning_settings.sql

INSERT INTO auth.users (id) VALUES ('a3000000-0000-0000-0000-00000000000a'), ('b3000000-0000-0000-0000-00000000000b') ON CONFLICT DO NOTHING;
INSERT INTO public.learning_settings (user_id, desired_retention) VALUES ('b3000000-0000-0000-0000-00000000000b', 0.85);

SET ROLE authenticated;
SELECT set_config('test.uid', 'a3000000-0000-0000-0000-00000000000a', false);
DO $$ DECLARE n INTEGER; BEGIN
    INSERT INTO public.learning_settings (desired_retention) VALUES (0.92)
    ON CONFLICT (user_id) DO UPDATE SET desired_retention = EXCLUDED.desired_retention;
    SELECT count(*) INTO n FROM public.learning_settings; IF n <> 1 THEN RAISE EXCEPTION 'a sees % rows', n; END IF;
    UPDATE public.learning_settings SET desired_retention = 0.80 WHERE user_id = 'b3000000-0000-0000-0000-00000000000b';
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'a changed b''s settings'; END IF;
    BEGIN UPDATE public.learning_settings SET desired_retention = 0.99; RAISE EXCEPTION 'retention 0.99 accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN INSERT INTO public.learning_settings (user_id) VALUES ('b3000000-0000-0000-0000-00000000000b'); RAISE EXCEPTION 'a wrote b''s row';
    EXCEPTION WHEN insufficient_privilege OR unique_violation THEN NULL; END;
END $$;
RESET ROLE;
SET ROLE anon;
DO $$ BEGIN
    BEGIN PERFORM 1 FROM public.learning_settings; RAISE EXCEPTION 'anon read settings';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;
DELETE FROM auth.users WHERE id IN ('a3000000-0000-0000-0000-00000000000a', 'b3000000-0000-0000-0000-00000000000b');
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.learning_settings WHERE user_id IN ('a3000000-0000-0000-0000-00000000000a', 'b3000000-0000-0000-0000-00000000000b')) THEN
        RAISE EXCEPTION 'settings survived account deletion';
    END IF;
    RAISE NOTICE '>> test_20_learning_settings: ALL CHECKS PASSED';
END $$;
