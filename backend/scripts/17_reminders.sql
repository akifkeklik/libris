-- =============================================================================
-- 17: Review reminders (Faz 3) — preferences, send log, least-privilege worker
-- =============================================================================
-- Tables
--   reminder_preferences  one row per reader: channel (email/push/off), local send time, IANA
--                         time zone, quiet weekdays, language, the e-mail captured from the
--                         reader's own session when they save, and a random unsubscribe token.
--                         RLS: a reader sees and changes only their own row.
--   reminder_sends        one row per reader per local date and channel: makes the daily send
--                         idempotent (a second run on the same day sends nothing).
-- Functions
--   reminders_unsubscribe(token)  SECURITY DEFINER, callable by anon: turns reminders off for
--                         the row holding that token (one-click unsubscribe / List-Unsubscribe).
--   reminder_candidates(now)      SECURITY DEFINER for the worker only: readers whose local hour
--                         has come, not quiet today, not yet sent today, with due items.
-- Role
--   reminder_worker       NOLOGIN here; the operator gives it a password (see the Faz 3 report).
--                         It can execute reminder_candidates and write reminder_sends, nothing else.
-- Idempotent: safe to run more than once. Depends on 10 (note_reviews) and 13 (review_items).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.reminder_preferences (
    user_id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    channel           TEXT NOT NULL DEFAULT 'email' CHECK (channel IN ('email', 'push', 'off')),
    local_time        TIME NOT NULL DEFAULT '09:00',
    timezone          TEXT NOT NULL DEFAULT 'UTC' CHECK (length(timezone) BETWEEN 1 AND 64),
    quiet_days        SMALLINT[] NOT NULL DEFAULT '{}' CHECK (quiet_days <@ ARRAY[0,1,2,3,4,5,6]::SMALLINT[]),
    language          TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'tr', 'de', 'es', 'fr', 'it')),
    email             TEXT CHECK (email IS NULL OR email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    unsubscribe_token UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.reminder_sends (
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    local_date DATE NOT NULL,
    channel    TEXT NOT NULL CHECK (channel IN ('email', 'push')),
    due_count  INTEGER NOT NULL DEFAULT 0,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, local_date, channel)
);

ALTER TABLE public.reminder_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reminder_sends ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage their own reminder preferences" ON public.reminder_preferences;
CREATE POLICY "Users manage their own reminder preferences" ON public.reminder_preferences
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reminder_worker') THEN
        CREATE ROLE reminder_worker NOLOGIN;
    END IF;
END $$;

-- RLS applies to the worker too: it may read and record sends, for every reader, and nothing else.
DROP POLICY IF EXISTS "Worker reads sends" ON public.reminder_sends;
CREATE POLICY "Worker reads sends" ON public.reminder_sends FOR SELECT TO reminder_worker USING (true);
DROP POLICY IF EXISTS "Worker records sends" ON public.reminder_sends;
CREATE POLICY "Worker records sends" ON public.reminder_sends FOR INSERT TO reminder_worker WITH CHECK (true);

DROP POLICY IF EXISTS "Users see their own reminder sends" ON public.reminder_sends;
CREATE POLICY "Users see their own reminder sends" ON public.reminder_sends
    FOR SELECT USING (auth.uid() = user_id);

-- A timezone the database does not know would make every candidate query fail.
CREATE OR REPLACE FUNCTION public.reminder_preferences_check_tz()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = NEW.timezone) THEN
        RAISE EXCEPTION 'unknown time zone: %', NEW.timezone USING ERRCODE = '22023';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS reminder_preferences_check_tz ON public.reminder_preferences;
CREATE TRIGGER reminder_preferences_check_tz BEFORE INSERT OR UPDATE ON public.reminder_preferences
    FOR EACH ROW EXECUTE FUNCTION public.reminder_preferences_check_tz();

CREATE OR REPLACE FUNCTION public.reminders_unsubscribe(p_token UUID)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n INTEGER;
BEGIN
    UPDATE public.reminder_preferences SET channel = 'off' WHERE unsubscribe_token = p_token;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n > 0;
END $$;

CREATE OR REPLACE FUNCTION public.reminder_candidates(p_now TIMESTAMPTZ DEFAULT now())
RETURNS TABLE (user_id UUID, email TEXT, language TEXT, local_date DATE, unsubscribe_token UUID,
               due_count INTEGER, first_question TEXT)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    WITH prefs AS (
        SELECT p.*, (p_now AT TIME ZONE p.timezone) AS local_ts
        FROM public.reminder_preferences p
        WHERE p.channel = 'email' AND p.email IS NOT NULL
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
    SELECT pr.user_id, pr.email, pr.language, pr.local_ts::date, pr.unsubscribe_token,
           d.due_count::INTEGER, d.first_question
    FROM prefs pr JOIN due d USING (user_id)
    WHERE d.due_count > 0
      AND pr.local_ts::time >= pr.local_time                       -- the reader's hour has come
      AND NOT (EXTRACT(DOW FROM pr.local_ts)::SMALLINT = ANY (pr.quiet_days))
      AND NOT EXISTS (SELECT 1 FROM public.reminder_sends s
                      WHERE s.user_id = pr.user_id AND s.local_date = pr.local_ts::date AND s.channel = 'email');
$$;

REVOKE ALL ON FUNCTION public.reminders_unsubscribe(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reminder_candidates(TIMESTAMPTZ) FROM PUBLIC;
DO $$
BEGIN
    GRANT USAGE ON SCHEMA public TO reminder_worker;
    GRANT EXECUTE ON FUNCTION public.reminder_candidates(TIMESTAMPTZ) TO reminder_worker;
    GRANT SELECT, INSERT ON public.reminder_sends TO reminder_worker;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        GRANT EXECUTE ON FUNCTION public.reminders_unsubscribe(UUID) TO anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.reminders_unsubscribe(UUID) TO authenticated;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.reminder_preferences TO authenticated;
        GRANT SELECT ON public.reminder_sends TO authenticated;
    END IF;
END $$;

COMMIT;
