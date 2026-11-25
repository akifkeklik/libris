-- Migration 21 on a database with Supabase's default grants. Throwaway database only.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
END $$;
GRANT USAGE ON SCHEMA public TO anon, authenticated;
-- What Supabase does by default:
GRANT ALL ON FUNCTION public.reminder_candidates(TIMESTAMPTZ), public.reminder_push_candidates(TIMESTAMPTZ),
    public.push_subscribe(TEXT, TEXT, TEXT) TO anon, authenticated;
GRANT ALL ON TABLE public.user_notes, public.review_items, public.reminder_preferences, public.product_events
    TO anon, authenticated;
SET ROLE anon;
SELECT count(*) FROM public.reminder_candidates(now());  -- works before 21: the hole is reproduced
RESET ROLE;
\ir ../../scripts/21_revoke_default_privileges.sql
\ir ../../scripts/21_revoke_default_privileges.sql
SET ROLE anon;
DO $$ BEGIN
    BEGIN PERFORM * FROM public.reminder_candidates(now()); RAISE EXCEPTION 'anon listed reminder candidates';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN PERFORM 1 FROM public.user_notes; RAISE EXCEPTION 'anon read notes';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    PERFORM public.reminders_unsubscribe(gen_random_uuid());
END $$;
RESET ROLE;
SET ROLE reminder_worker;
SELECT count(*) FROM public.reminder_candidates(now());
RESET ROLE;
DO $$ BEGIN RAISE NOTICE '>> test_21: ALL CHECKS PASSED'; END $$;
