-- Runtime checks for migration 17 (reminders). Throwaway database only.
-- Fixed clock: 2026-11-23 06:30 UTC is a Monday; 09:30 in Istanbul, 01:30 in New York.

CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('test.uid', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
$$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
END $$;
GRANT USAGE ON SCHEMA public, auth TO authenticated, anon;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated, anon;
-- Migration 17 grants to these roles only if they existed when it ran; re-apply now that they do.
\ir ../../scripts/17_reminders.sql

INSERT INTO auth.users (id) VALUES
  ('a0000000-0000-0000-0000-00000000000a'), ('b0000000-0000-0000-0000-00000000000b'),
  ('c0000000-0000-0000-0000-00000000000c'), ('d0000000-0000-0000-0000-00000000000d'),
  ('e0000000-0000-0000-0000-00000000000e')
ON CONFLICT DO NOTHING;

-- a: Istanbul 09:00, due -> candidate. b: New York (01:30 local) -> not yet. c: quiet on Monday.
-- d: channel off. e: no due items.
INSERT INTO public.reminder_preferences (user_id, channel, local_time, timezone, quiet_days, language, email) VALUES
  ('a0000000-0000-0000-0000-00000000000a', 'email', '09:00', 'Europe/Istanbul', '{}', 'tr', 'a@example.com'),
  ('b0000000-0000-0000-0000-00000000000b', 'email', '09:00', 'America/New_York', '{}', 'en', 'b@example.com'),
  ('c0000000-0000-0000-0000-00000000000c', 'email', '09:00', 'Europe/Istanbul', '{1}', 'en', 'c@example.com'),
  ('d0000000-0000-0000-0000-00000000000d', 'off',   '09:00', 'Europe/Istanbul', '{}', 'en', 'd@example.com'),
  ('e0000000-0000-0000-0000-00000000000e', 'email', '09:00', 'Europe/Istanbul', '{}', 'en', 'e@example.com');
INSERT INTO public.review_items (user_id, title, concept, question, answer, source_type, next_review_at)
SELECT u, 'T', 'C', 'What is the main idea of 1984?', 'Surveillance', 'key_takeaway', '2026-11-22 12:00+00'
FROM unnest(ARRAY['a0000000-0000-0000-0000-00000000000a', 'b0000000-0000-0000-0000-00000000000b',
                  'c0000000-0000-0000-0000-00000000000c', 'd0000000-0000-0000-0000-00000000000d']::uuid[]) AS u;

DO $$
DECLARE n INTEGER; r RECORD;
BEGIN
    -- 1. Only reader a is due at this moment, with the count, first question and local date.
    SELECT count(*) INTO n FROM public.reminder_candidates('2026-11-23 06:30+00');
    IF n <> 1 THEN RAISE EXCEPTION 'expected 1 candidate, got %', n; END IF;
    SELECT * INTO r FROM public.reminder_candidates('2026-11-23 06:30+00');
    IF r.user_id <> 'a0000000-0000-0000-0000-00000000000a' OR r.due_count <> 1 OR r.language <> 'tr'
       OR r.local_date <> '2026-11-23' OR r.first_question <> 'What is the main idea of 1984?' THEN
        RAISE EXCEPTION 'wrong candidate row: %', r;
    END IF;
    -- 2. Later the same day, New York's 09:00 has come: b becomes due, a still is.
    SELECT count(*) INTO n FROM public.reminder_candidates('2026-11-23 14:30+00');
    IF n <> 2 THEN RAISE EXCEPTION 'expected a and b at 14:30 UTC, got %', n; END IF;
    -- 3. After a send is recorded for a's local date, a is not a candidate again that day.
    INSERT INTO public.reminder_sends (user_id, local_date, channel, due_count)
    VALUES ('a0000000-0000-0000-0000-00000000000a', '2026-11-23', 'email', 1);
    SELECT count(*) INTO n FROM public.reminder_candidates('2026-11-23 06:30+00');
    IF n <> 0 THEN RAISE EXCEPTION 'a was offered twice on the same day'; END IF;
    BEGIN
        INSERT INTO public.reminder_sends (user_id, local_date, channel) VALUES ('a0000000-0000-0000-0000-00000000000a', '2026-11-23', 'email');
        RAISE EXCEPTION 'duplicate send row accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    -- 4. The next day a is due again.
    SELECT count(*) INTO n FROM public.reminder_candidates('2026-11-24 06:30+00') WHERE user_id = 'a0000000-0000-0000-0000-00000000000a';
    IF n <> 1 THEN RAISE EXCEPTION 'a not offered on the next day'; END IF;

    -- 5. Unknown time zones are rejected.
    BEGIN
        UPDATE public.reminder_preferences SET timezone = 'Mars/Olympus' WHERE user_id = 'e0000000-0000-0000-0000-00000000000e';
        RAISE EXCEPTION 'unknown time zone accepted';
    EXCEPTION WHEN invalid_parameter_value THEN NULL;
    END;

    -- 6. Unsubscribe by token turns the channel off; a wrong token does nothing.
    IF public.reminders_unsubscribe(gen_random_uuid()) THEN RAISE EXCEPTION 'random token unsubscribed someone'; END IF;
    IF NOT public.reminders_unsubscribe((SELECT unsubscribe_token FROM public.reminder_preferences
                                         WHERE user_id = 'b0000000-0000-0000-0000-00000000000b')) THEN
        RAISE EXCEPTION 'valid token did not unsubscribe';
    END IF;
    IF (SELECT channel FROM public.reminder_preferences WHERE user_id = 'b0000000-0000-0000-0000-00000000000b') <> 'off' THEN
        RAISE EXCEPTION 'channel not off after unsubscribe';
    END IF;
END $$;

-- 7. RLS: a reader sees only their own preferences.
SET ROLE authenticated;
SELECT set_config('test.uid', 'a0000000-0000-0000-0000-00000000000a', false);
DO $$ DECLARE n INTEGER; BEGIN
    SELECT count(*) INTO n FROM public.reminder_preferences; IF n <> 1 THEN RAISE EXCEPTION 'a sees % preference rows', n; END IF;
    UPDATE public.reminder_preferences SET channel = 'off' WHERE user_id = 'c0000000-0000-0000-0000-00000000000c';
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'a changed c''s preferences'; END IF;
END $$;
RESET ROLE;

-- 8. The worker role: candidates and the send log only.
SET ROLE reminder_worker;
DO $$ DECLARE n INTEGER; BEGIN
    SELECT count(*) INTO n FROM public.reminder_candidates('2026-11-24 06:30+00');
    INSERT INTO public.reminder_sends (user_id, local_date, channel) VALUES ('a0000000-0000-0000-0000-00000000000a', '2026-11-24', 'email');
    BEGIN PERFORM 1 FROM public.review_items LIMIT 1; RAISE EXCEPTION 'worker read review_items directly';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN PERFORM 1 FROM public.reminder_preferences LIMIT 1; RAISE EXCEPTION 'worker read preferences (e-mails) directly';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;

-- 9. anon may unsubscribe (link in the e-mail) but not list candidates.
SET ROLE anon;
DO $$ BEGIN
    BEGIN PERFORM 1 FROM public.reminder_candidates(now()); RAISE EXCEPTION 'anon listed reminder candidates';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    PERFORM public.reminders_unsubscribe(gen_random_uuid());
END $$;
RESET ROLE;

DO $$ BEGIN RAISE NOTICE '>> test_17_reminders: ALL CHECKS PASSED'; END $$;
DELETE FROM auth.users WHERE id::text LIKE '_0000000-0000-0000-0000-00000000000_';
