-- 18_push_and_events.sql — Faz 3, part 2: Web Push subscriptions and product events.
-- Requires 17_reminders.sql (and, through it, 09/10/13). Idempotent: safe to run more than once.
--
--   push_subscriptions   one row per browser/device a reader allowed notifications on. Owned by
--                        the reader (RLS). The reminder worker may read them (to send) and delete
--                        them (when the push service answers 404/410: the subscription is gone).
--   reminder_push_candidates(now)
--                        same rules as reminder_candidates (due questions, local hour reached,
--                        not a quiet day, not yet sent today) for readers whose channel is 'push'
--                        and who have at least one subscription.
--   product_events       first-party product events a signed-in reader's app reports about
--                        itself: reminder_opened, review_session_completed. reminder_sent is the
--                        reminder_sends table. Insert-only for readers; no reader can read events.
--
-- Rollback: scripts/rollbacks/18_push_and_events_rollback.sql

CREATE TABLE IF NOT EXISTS public.push_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    endpoint    TEXT NOT NULL UNIQUE CHECK (endpoint ~ '^https://' AND length(endpoint) <= 1024),
    p256dh      TEXT NOT NULL CHECK (length(p256dh) BETWEEN 40 AND 200),
    auth        TEXT NOT NULL CHECK (length(auth) BETWEEN 8 AND 100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS push_subscriptions_user_idx ON public.push_subscriptions (user_id);

CREATE TABLE IF NOT EXISTS public.product_events (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      UUID NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
    event        TEXT NOT NULL CHECK (event IN ('reminder_opened', 'review_session_completed')),
    props        JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(props) = 'object' AND length(props::text) <= 512),
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS product_events_event_time_idx ON public.product_events (event, occurred_at);

ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_events ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reminder_worker') THEN
        CREATE ROLE reminder_worker NOLOGIN;
    END IF;
END $$;

DROP POLICY IF EXISTS push_subscriptions_own ON public.push_subscriptions;
CREATE POLICY push_subscriptions_own ON public.push_subscriptions
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS push_subscriptions_worker_read ON public.push_subscriptions;
CREATE POLICY push_subscriptions_worker_read ON public.push_subscriptions
    FOR SELECT TO reminder_worker USING (true);
DROP POLICY IF EXISTS push_subscriptions_worker_delete ON public.push_subscriptions;
CREATE POLICY push_subscriptions_worker_delete ON public.push_subscriptions
    FOR DELETE TO reminder_worker USING (true);

DROP POLICY IF EXISTS product_events_insert_own ON public.product_events;
CREATE POLICY product_events_insert_own ON public.product_events
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.reminder_push_candidates(p_now TIMESTAMPTZ DEFAULT now())
RETURNS TABLE (user_id UUID, language TEXT, local_date DATE, due_count INTEGER, first_question TEXT)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    WITH prefs AS (
        SELECT p.*, (p_now AT TIME ZONE p.timezone) AS local_ts
        FROM public.reminder_preferences p
        WHERE p.channel = 'push'
          AND EXISTS (SELECT 1 FROM public.push_subscriptions ps WHERE ps.user_id = p.user_id)
    ), due AS (
        SELECT pr.user_id,
               (SELECT count(*) FROM public.review_items ri
                 WHERE ri.user_id = pr.user_id AND ri.status = 'active' AND ri.next_review_at <= p_now)
             + (SELECT count(*) FROM public.note_reviews nr
                 WHERE nr.user_id = pr.user_id AND nr.next_review_at <= p_now) AS due_count,
               (SELECT ri.question FROM public.review_items ri
                 WHERE ri.user_id = pr.user_id AND ri.status = 'active' AND ri.next_review_at <= p_now
                 ORDER BY ri.next_review_at LIMIT 1) AS first_question
        FROM prefs pr
    )
    SELECT pr.user_id, pr.language, pr.local_ts::date, d.due_count::INTEGER, d.first_question
    FROM prefs pr JOIN due d USING (user_id)
    WHERE d.due_count > 0
      AND pr.local_ts::time >= pr.local_time
      AND NOT (EXTRACT(DOW FROM pr.local_ts)::SMALLINT = ANY (pr.quiet_days))
      AND NOT EXISTS (SELECT 1 FROM public.reminder_sends s
                      WHERE s.user_id = pr.user_id AND s.local_date = pr.local_ts::date AND s.channel = 'push');
$$;

-- Saves the calling reader's subscription. A push endpoint is an unguessable capability URL held
-- by one browser, so when that browser signs in to another account the endpoint moves to the new
-- account (otherwise the previous account would keep receiving its reminders). At most 10
-- devices per reader; the oldest are dropped.
CREATE OR REPLACE FUNCTION public.push_subscribe(p_endpoint TEXT, p_p256dh TEXT, p_auth TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE uid UUID := auth.uid();
BEGIN
    IF uid IS NULL THEN RAISE EXCEPTION 'not signed in' USING ERRCODE = '42501'; END IF;
    DELETE FROM public.push_subscriptions WHERE endpoint = p_endpoint;
    -- clock_timestamp(): now() is fixed for a whole transaction, which made "newest" a coin toss.
    INSERT INTO public.push_subscriptions (user_id, endpoint, p256dh, auth, created_at)
    VALUES (uid, p_endpoint, p_p256dh, p_auth, clock_timestamp());
    DELETE FROM public.push_subscriptions WHERE id IN (
        SELECT id FROM public.push_subscriptions WHERE user_id = uid
        ORDER BY (endpoint = p_endpoint) DESC, created_at DESC, id OFFSET 10);
END $$;

REVOKE ALL ON FUNCTION public.push_subscribe(TEXT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reminder_push_candidates(TIMESTAMPTZ) FROM PUBLIC;
REVOKE ALL ON public.push_subscriptions FROM PUBLIC;
REVOKE ALL ON public.product_events FROM PUBLIC;
DO $$
BEGIN
    GRANT EXECUTE ON FUNCTION public.reminder_push_candidates(TIMESTAMPTZ) TO reminder_worker;
    GRANT SELECT, DELETE ON public.push_subscriptions TO reminder_worker;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT SELECT, INSERT, DELETE ON public.push_subscriptions TO authenticated;
        GRANT INSERT ON public.product_events TO authenticated;
        GRANT EXECUTE ON FUNCTION public.push_subscribe(TEXT, TEXT, TEXT) TO authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.push_subscriptions FROM anon;
        REVOKE ALL ON public.product_events FROM anon;
    END IF;
END $$;
