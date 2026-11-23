-- Runtime checks for migration 18 (push subscriptions, push candidates, product events).
-- Throwaway database only. Fixed clock: 2026-11-23 06:30 UTC (09:30 in Istanbul).

CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('test.uid', true), ''), '00000000-0000-0000-0000-000000000000')::uuid
$$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
END $$;
GRANT USAGE ON SCHEMA public, auth TO authenticated, anon;
GRANT EXECUTE ON FUNCTION auth.uid() TO authenticated, anon;
-- Re-apply now that the roles exist (grants are conditional); twice for 18 to prove idempotency.
\ir ../../scripts/17_reminders.sql
\ir ../../scripts/18_push_and_events.sql
\ir ../../scripts/18_push_and_events.sql

INSERT INTO auth.users (id) VALUES
  ('a1000000-0000-0000-0000-00000000000a'), ('b1000000-0000-0000-0000-00000000000b'),
  ('c1000000-0000-0000-0000-00000000000c')
ON CONFLICT DO NOTHING;
-- a: push with a subscription -> candidate. b: push without a subscription -> not. c: e-mail -> not a push candidate.
INSERT INTO public.reminder_preferences (user_id, channel, local_time, timezone, language, email) VALUES
  ('a1000000-0000-0000-0000-00000000000a', 'push',  '09:00', 'Europe/Istanbul', 'de', NULL),
  ('b1000000-0000-0000-0000-00000000000b', 'push',  '09:00', 'Europe/Istanbul', 'en', NULL),
  ('c1000000-0000-0000-0000-00000000000c', 'email', '09:00', 'Europe/Istanbul', 'en', 'c1@example.com');
INSERT INTO public.review_items (user_id, title, concept, question, answer, source_type, next_review_at)
SELECT u, 'T', 'C', 'Q?', 'A', 'key_takeaway', '2026-11-22 12:00+00'
FROM unnest(ARRAY['a1000000-0000-0000-0000-00000000000a', 'b1000000-0000-0000-0000-00000000000b',
                  'c1000000-0000-0000-0000-00000000000c']::uuid[]) AS u;
INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth) VALUES
  ('a1000000-0000-0000-0000-00000000000a', 'https://push.example/a1', repeat('k', 87), repeat('s', 22));

DO $$
DECLARE n INTEGER; r RECORD;
BEGIN
    SELECT count(*) INTO n FROM public.reminder_push_candidates('2026-11-23 06:30+00');
    IF n <> 1 THEN RAISE EXCEPTION 'expected 1 push candidate, got %', n; END IF;
    SELECT * INTO r FROM public.reminder_push_candidates('2026-11-23 06:30+00');
    IF r.user_id <> 'a1000000-0000-0000-0000-00000000000a' OR r.language <> 'de' OR r.due_count <> 1 THEN
        RAISE EXCEPTION 'wrong push candidate: %', r;
    END IF;
    -- E-mail candidates do not include push readers.
    SELECT count(*) INTO n FROM public.reminder_candidates('2026-11-23 06:30+00') WHERE user_id::text LIKE '_1000000%';
    IF n <> 1 THEN RAISE EXCEPTION 'e-mail candidates should be c only, got %', n; END IF;
    -- A push send for the local date ends the push offer for that day.
    INSERT INTO public.reminder_sends (user_id, local_date, channel) VALUES ('a1000000-0000-0000-0000-00000000000a', '2026-11-23', 'push');
    SELECT count(*) INTO n FROM public.reminder_push_candidates('2026-11-23 06:30+00');
    IF n <> 0 THEN RAISE EXCEPTION 'push offered twice on the same day'; END IF;
    -- Non-https endpoints are rejected.
    BEGIN
        INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth)
        VALUES ('b1000000-0000-0000-0000-00000000000b', 'http://evil.example/x', repeat('k', 87), repeat('s', 22));
        RAISE EXCEPTION 'http endpoint accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END $$;

-- RLS: a reader manages only their own subscriptions and can write, but not read, events.
INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth) VALUES
  ('b1000000-0000-0000-0000-00000000000b', 'https://push.example/b1', repeat('k', 87), repeat('s', 22));
SET ROLE authenticated;
SELECT set_config('test.uid', 'a1000000-0000-0000-0000-00000000000a', false);
DO $$ DECLARE n INTEGER; BEGIN
    SELECT count(*) INTO n FROM public.push_subscriptions; IF n <> 1 THEN RAISE EXCEPTION 'a sees % subscriptions', n; END IF;
    DELETE FROM public.push_subscriptions WHERE endpoint = 'https://push.example/b1';
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'a deleted b''s subscription'; END IF;
    BEGIN
        INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth)
        VALUES ('b1000000-0000-0000-0000-00000000000b', 'https://push.example/forged', repeat('k', 87), repeat('s', 22));
        RAISE EXCEPTION 'a created a subscription for b';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    INSERT INTO public.product_events (event, props) VALUES ('reminder_opened', '{"channel":"push"}');
    BEGIN
        INSERT INTO public.product_events (user_id, event) VALUES ('b1000000-0000-0000-0000-00000000000b', 'reminder_opened');
        RAISE EXCEPTION 'a wrote an event as b';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO public.product_events (event) VALUES ('page_view');
        RAISE EXCEPTION 'unknown event accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN PERFORM 1 FROM public.product_events; RAISE EXCEPTION 'reader read product events';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    -- push_subscribe: b's browser signs in as a -> the endpoint moves to a; a keeps at most 10 devices.
    PERFORM public.push_subscribe('https://push.example/b1', repeat('k', 87), repeat('s', 22));
    FOR i IN 1..12 LOOP
        PERFORM public.push_subscribe('https://push.example/a-dev-' || i, repeat('k', 87), repeat('s', 22));
    END LOOP;
    SELECT count(*) INTO n FROM public.push_subscriptions; IF n <> 10 THEN RAISE EXCEPTION 'a has % devices, expected 10', n; END IF;
    IF NOT EXISTS (SELECT 1 FROM public.push_subscriptions WHERE endpoint = 'https://push.example/a-dev-12') THEN
        RAISE EXCEPTION 'newest device was dropped';
    END IF;
END $$;
RESET ROLE;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.push_subscriptions WHERE endpoint = 'https://push.example/b1'
               AND user_id = 'b1000000-0000-0000-0000-00000000000b') THEN
        RAISE EXCEPTION 'endpoint did not move to the account now signed in';
    END IF;
    -- Put b's device back for the worker checks below.
    INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth)
    VALUES ('b1000000-0000-0000-0000-00000000000b', 'https://push.example/b2', repeat('k', 87), repeat('s', 22));
END $$;

-- Worker: reads and deletes subscriptions (410 cleanup), cannot add them or read events.
SET ROLE reminder_worker;
DO $$ DECLARE n INTEGER; BEGIN
    SELECT count(*) INTO n FROM public.push_subscriptions; IF n <> 11 THEN RAISE EXCEPTION 'worker sees % subscriptions', n; END IF;
    DELETE FROM public.push_subscriptions WHERE endpoint = 'https://push.example/b2';
    GET DIAGNOSTICS n = ROW_COUNT; IF n <> 1 THEN RAISE EXCEPTION 'worker could not remove a gone subscription'; END IF;
    BEGIN
        INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth)
        VALUES ('b1000000-0000-0000-0000-00000000000b', 'https://push.example/w', repeat('k', 87), repeat('s', 22));
        RAISE EXCEPTION 'worker inserted a subscription';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN PERFORM 1 FROM public.product_events; RAISE EXCEPTION 'worker read product events';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;

-- anon: nothing.
SET ROLE anon;
DO $$ BEGIN
    BEGIN PERFORM 1 FROM public.push_subscriptions; RAISE EXCEPTION 'anon read subscriptions';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN PERFORM 1 FROM public.reminder_push_candidates(now()); RAISE EXCEPTION 'anon listed push candidates';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET ROLE;

-- Account deletion cascades.
DELETE FROM auth.users WHERE id = 'a1000000-0000-0000-0000-00000000000a';
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.push_subscriptions WHERE user_id = 'a1000000-0000-0000-0000-00000000000a')
       OR EXISTS (SELECT 1 FROM public.product_events WHERE user_id = 'a1000000-0000-0000-0000-00000000000a') THEN
        RAISE EXCEPTION 'subscriptions or events survived account deletion';
    END IF;
    RAISE NOTICE '>> test_18_push_and_events: ALL CHECKS PASSED';
END $$;
DELETE FROM auth.users WHERE id::text LIKE '_1000000-0000-0000-0000-00000000000_';
