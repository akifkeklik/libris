-- Production rollout, one paste: Supabase Dashboard -> SQL Editor -> paste all -> Run.
-- GENERATED from migrations 09, 10, 13, 16-21 (backend/scripts); the numbered files stay the source.
-- One transaction: if anything fails, or any existing row count changes, nothing is saved.
-- Adds tables; deletes no data. 16 re-creates two foreign keys as ON DELETE CASCADE.
-- Expected last message: "ROLLOUT OK". Take a backup first (Dashboard -> Database -> Backups).
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';
-- Row counts live in a transaction-local setting, not a temp table: the SQL Editor offers to enable RLS
-- on every created table and then fails on a temp table that is already gone after COMMIT.
SELECT set_config('libris.rows_before', concat_ws(',', (SELECT count(*) FROM public.books), (SELECT count(*) FROM public.favorites),
    (SELECT count(*) FROM public.user_activities), (SELECT count(*) FROM public.user_interactions)), true);

-- ===== 09_learning_notes.sql =====
-- migration: Create user_notes table for learning companion and knowledge retention
-- Description: Stores personal notes, key takeaways, and research questions associated with books and users.

CREATE TABLE IF NOT EXISTS public.user_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL, -- references isbn13 from books table
    note_type TEXT NOT NULL CHECK (note_type IN ('personal_note', 'key_takeaway', 'question')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast lookup of a user's notes for a specific book
CREATE INDEX IF NOT EXISTS idx_user_notes_user_book ON public.user_notes(user_id, book_id);

-- Index for filtering a user's notes by note type
CREATE INDEX IF NOT EXISTS idx_user_notes_user_type ON public.user_notes(user_id, note_type);

-- Index for chronological ordering of notes
CREATE INDEX IF NOT EXISTS idx_user_notes_user_created ON public.user_notes(user_id, created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE public.user_notes ENABLE ROW LEVEL SECURITY;

-- Allow users to view only their own notes
DROP POLICY IF EXISTS "Users can view their own notes" ON public.user_notes;
CREATE POLICY "Users can view their own notes" 
ON public.user_notes FOR SELECT 
USING (auth.uid() = user_id);

-- Allow users to create their own notes
DROP POLICY IF EXISTS "Users can insert their own notes" ON public.user_notes;
CREATE POLICY "Users can insert their own notes" 
ON public.user_notes FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Allow users to update their own notes
DROP POLICY IF EXISTS "Users can update their own notes" ON public.user_notes;
CREATE POLICY "Users can update their own notes" 
ON public.user_notes FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Allow users to delete their own notes
DROP POLICY IF EXISTS "Users can delete their own notes" ON public.user_notes;
CREATE POLICY "Users can delete their own notes" 
ON public.user_notes FOR DELETE 
USING (auth.uid() = user_id);

-- ===== 10_learning_notes_idempotency_and_review.sql =====
-- migration: 10_learning_notes_idempotency_and_review.sql
-- Description: Adds client_id idempotency support to user_notes and introduces note_reviews table for Spaced Repetition (Smart Review).

-- 1. Add client_id for offline-first idempotency and deduplication
ALTER TABLE public.user_notes
ADD COLUMN IF NOT EXISTS client_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_notes_user_client_id
ON public.user_notes (user_id, client_id)
WHERE client_id IS NOT NULL;

-- 2. Create note_reviews table for Spaced Repetition & Smart Review
CREATE TABLE IF NOT EXISTS public.note_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID NOT NULL REFERENCES public.user_notes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stage INT NOT NULL DEFAULT 1 CHECK (stage >= 1 AND stage <= 4),
    interval_days INT NOT NULL DEFAULT 1,
    next_review_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 day'),
    last_reviewed_at TIMESTAMPTZ,
    review_count INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_note_review_user_note UNIQUE (user_id, note_id)
);

-- Index for querying due reviews efficiently
CREATE INDEX IF NOT EXISTS idx_note_reviews_user_due
ON public.note_reviews (user_id, status, next_review_at);

-- 3. Row Level Security (RLS)
ALTER TABLE public.note_reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own note reviews" ON public.note_reviews;
CREATE POLICY "Users can view their own note reviews"
ON public.note_reviews FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own note reviews" ON public.note_reviews;
CREATE POLICY "Users can insert their own note reviews"
ON public.note_reviews FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own note reviews" ON public.note_reviews;
CREATE POLICY "Users can update their own note reviews"
ON public.note_reviews FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own note reviews" ON public.note_reviews;
CREATE POLICY "Users can delete their own note reviews"
ON public.note_reviews FOR DELETE
USING (auth.uid() = user_id);

-- ===== 13_learning_outcomes.sql =====
-- migration: 13_learning_outcomes.sql
-- Description: Creates review_items and review_attempts tables for Learning Outcomes Intelligence with RLS, indexes, and cascade constraints.

CREATE TABLE IF NOT EXISTS public.review_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    concept TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    explanation TEXT DEFAULT '',
    source_type TEXT NOT NULL CHECK (source_type IN ('user_note', 'key_takeaway', 'concept', 'learning_path', 'user_created', 'book')),
    source_id TEXT DEFAULT NULL,
    book_id TEXT DEFAULT NULL,
    path_id TEXT DEFAULT NULL,
    stage INT NOT NULL DEFAULT 1 CHECK (stage >= 1 AND stage <= 5),
    interval_days INT NOT NULL DEFAULT 1,
    next_review_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 day'),
    last_reviewed_at TIMESTAMPTZ DEFAULT NULL,
    total_reviews INT NOT NULL DEFAULT 0,
    successful_reviews INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_review_items_user_due
ON public.review_items (user_id, status, next_review_at);

CREATE INDEX IF NOT EXISTS idx_review_items_user_concept
ON public.review_items (user_id, concept);

CREATE INDEX IF NOT EXISTS idx_review_items_source
ON public.review_items (user_id, source_type, source_id);

CREATE TABLE IF NOT EXISTS public.review_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES public.review_items(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN ('remembered', 'struggled')),
    response_text TEXT DEFAULT '',
    is_correct BOOLEAN NOT NULL DEFAULT false,
    stage_before INT NOT NULL DEFAULT 1,
    stage_after INT NOT NULL DEFAULT 1,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_review_attempts_user_date
ON public.review_attempts (user_id, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_attempts_item
ON public.review_attempts (item_id, reviewed_at DESC);

-- Row Level Security (RLS)
ALTER TABLE public.review_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_attempts ENABLE ROW LEVEL SECURITY;

-- Policies for review_items
DROP POLICY IF EXISTS "Users can view their own review items" ON public.review_items;
CREATE POLICY "Users can view their own review items"
ON public.review_items FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own review items" ON public.review_items;
CREATE POLICY "Users can insert their own review items"
ON public.review_items FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own review items" ON public.review_items;
CREATE POLICY "Users can update their own review items"
ON public.review_items FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own review items" ON public.review_items;
CREATE POLICY "Users can delete their own review items"
ON public.review_items FOR DELETE
USING (auth.uid() = user_id);

-- Policies for review_attempts
DROP POLICY IF EXISTS "Users can view their own review attempts" ON public.review_attempts;
CREATE POLICY "Users can view their own review attempts"
ON public.review_attempts FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own review attempts" ON public.review_attempts;
CREATE POLICY "Users can insert their own review attempts"
ON public.review_attempts FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own review attempts" ON public.review_attempts;
CREATE POLICY "Users can delete their own review attempts"
ON public.review_attempts FOR DELETE
USING (auth.uid() = user_id);

-- ===== 16_account_deletion.sql =====
-- =============================================================================
-- 16: Self-service account deletion (KVKK / GDPR right to erasure)
-- =============================================================================
-- What it does:
--   1. Makes every foreign key from public.* to auth.users ON DELETE CASCADE.
--      Production (2026-11-22, read-only check): favorites.user_id and
--      user_activities.user_id were NO ACTION, so deleting such a user failed even
--      from the Supabase dashboard. Constraints are re-created NOT VALID so existing
--      orphan rows (if any) cannot block the migration; cascading works either way.
--   2. public.delete_my_account(): SECURITY DEFINER, deletes only the caller
--      (auth.uid()); clears books.added_by (the contributed book stays in the shared
--      catalog, the link to the person goes); deleting auth.users cascades to every
--      user table. Callable by `authenticated` only.
--
-- Why an RPC instead of the service-role key in the API: the runtime backend never
-- holds a service_role key (test_catalog_write_boundary.py). This function can only
-- ever delete the account whose JWT calls it.
--
-- Idempotent: safe to run more than once. Rollback: rollbacks/16_account_deletion_rollback.sql
-- =============================================================================

SET LOCAL lock_timeout = '5s';

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT c.conname, c.conrelid::regclass AS tbl, a.attname
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.contype = 'f'
          AND c.confrelid = 'auth.users'::regclass
          AND c.connamespace = 'public'::regnamespace
          AND c.confdeltype <> 'c'
          AND array_length(c.conkey, 1) = 1
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES auth.users(id) ON DELETE CASCADE NOT VALID',
            r.tbl, r.conname, r.attname);
        RAISE NOTICE '16: % (%) now ON DELETE CASCADE', r.tbl, r.attname;
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.delete_my_account()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user UUID := auth.uid();
BEGIN
    IF v_user IS NULL THEN
        RAISE EXCEPTION 'not authenticated' USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'books' AND column_name = 'added_by'
    ) THEN
        UPDATE public.books SET added_by = NULL WHERE added_by = v_user;
    END IF;

    DELETE FROM auth.users WHERE id = v_user;
END;
$$;

REVOKE ALL ON FUNCTION public.delete_my_account() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION public.delete_my_account() FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.delete_my_account() TO authenticated;
    END IF;
END $$;

-- ===== 17_reminders.sql =====
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
-- The worker claims a row before sending and deletes it if the provider fails, so the next run
-- retries instead of skipping the reader for the day.
DROP POLICY IF EXISTS "Worker releases failed sends" ON public.reminder_sends;
CREATE POLICY "Worker releases failed sends" ON public.reminder_sends FOR DELETE TO reminder_worker USING (true);

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
    GRANT SELECT, INSERT, DELETE ON public.reminder_sends TO reminder_worker;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        GRANT EXECUTE ON FUNCTION public.reminders_unsubscribe(UUID) TO anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.reminders_unsubscribe(UUID) TO authenticated;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.reminder_preferences TO authenticated;
        GRANT SELECT ON public.reminder_sends TO authenticated;
    END IF;
END $$;

-- ===== 18_push_and_events.sql =====
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

-- ===== 19_import_queue.sql =====
-- 19_import_queue.sql — Faz 4: approval queue for imported highlights, notes and shelves.
-- Requires 09 (user_notes). Idempotent: safe to run more than once.
--
-- Imported entries wait here (status 'pending') until the reader approves them (-> a note or a
-- library shelf) or dismisses them. content_hash is unique per reader, so re-importing the same
-- file, or the same highlight from another app, adds nothing; dismissed entries stay as
-- 'rejected' so they do not come back. Owned by the reader (RLS); at most 5000 pending entries.
--
-- Rollback: scripts/rollbacks/19_import_queue_rollback.sql

CREATE TABLE IF NOT EXISTS public.import_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
    source        TEXT NOT NULL CHECK (source IN ('kindle', 'readwise', 'goodreads', 'share')),
    kind          TEXT NOT NULL CHECK (kind IN ('highlight', 'note', 'shelf')),
    content_hash  TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    book_title    TEXT NOT NULL CHECK (length(book_title) BETWEEN 1 AND 500),
    book_author   TEXT CHECK (length(book_author) <= 300),
    book_id       TEXT CHECK (length(book_id) <= 64),
    content       TEXT CHECK (length(content) <= 5000),
    location      TEXT CHECK (length(location) <= 120),
    shelf         TEXT CHECK (shelf IN ('want_to_read', 'reading', 'finished')),
    rating        SMALLINT CHECK (rating BETWEEN 1 AND 5),
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    note_id       UUID REFERENCES public.user_notes(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at    TIMESTAMPTZ,
    CONSTRAINT import_items_user_hash UNIQUE (user_id, content_hash),
    CONSTRAINT import_items_shape CHECK (
        (kind = 'shelf' AND shelf IS NOT NULL AND content IS NULL)
        OR (kind <> 'shelf' AND content IS NOT NULL AND length(btrim(content)) > 0))
);
CREATE INDEX IF NOT EXISTS import_items_user_status_idx ON public.import_items (user_id, status, created_at);

ALTER TABLE public.import_items ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS import_items_own ON public.import_items;
CREATE POLICY import_items_own ON public.import_items
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Cap the queue per reader (the API checks too; this holds for direct PostgREST calls).
CREATE OR REPLACE FUNCTION public.import_items_cap()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT count(*) FROM public.import_items WHERE user_id = NEW.user_id AND status = 'pending') >= 5000 THEN
        RAISE EXCEPTION 'import queue full' USING ERRCODE = '54000';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS import_items_cap ON public.import_items;
CREATE TRIGGER import_items_cap BEFORE INSERT ON public.import_items
    FOR EACH ROW WHEN (NEW.status = 'pending') EXECUTE FUNCTION public.import_items_cap();

REVOKE ALL ON public.import_items FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.import_items TO authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.import_items FROM anon;
    END IF;
END $$;

-- ===== 20_learning_settings.sql =====
-- 20_learning_settings.sql — Faz 5: the reader's review settings (FSRS target retention).
-- Idempotent. Rollback: scripts/rollbacks/20_learning_settings_rollback.sql

CREATE TABLE IF NOT EXISTS public.learning_settings (
    user_id            UUID PRIMARY KEY DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
    desired_retention  NUMERIC(3, 2) NOT NULL DEFAULT 0.90 CHECK (desired_retention BETWEEN 0.80 AND 0.95),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.learning_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS learning_settings_own ON public.learning_settings;
CREATE POLICY learning_settings_own ON public.learning_settings
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

REVOKE ALL ON public.learning_settings FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT SELECT, INSERT, UPDATE ON public.learning_settings TO authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON public.learning_settings FROM anon;
    END IF;
END $$;

-- ===== 21_revoke_default_privileges.sql =====
-- 21_revoke_default_privileges.sql: closes what Supabase grants by default.
-- Supabase's default privileges give anon and authenticated EXECUTE on every new function and rights
-- on every new table. "REVOKE ... FROM PUBLIC" (17, 18) does not remove those direct grants, so anyone
-- could call the SECURITY DEFINER candidate functions (reader e-mails, questions, unsubscribe tokens).
-- Plain PostgreSQL has no such defaults, which is why CI did not see it.
-- Idempotent, deletes no data; one statement, so a failed check undoes everything. Expected: "21 OK".

DO $$
DECLARE r TEXT; t TEXT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        RAISE NOTICE '21 skipped: no Supabase API roles in this database';
        RETURN;
    END IF;

    REVOKE ALL ON FUNCTION public.reminder_candidates(TIMESTAMPTZ), public.reminder_push_candidates(TIMESTAMPTZ),
        public.push_subscribe(TEXT, TEXT, TEXT), public.reminder_preferences_check_tz(), public.import_items_cap()
        FROM PUBLIC, anon, authenticated;
    GRANT EXECUTE ON FUNCTION public.push_subscribe(TEXT, TEXT, TEXT) TO authenticated;
    GRANT EXECUTE ON FUNCTION public.reminder_candidates(TIMESTAMPTZ), public.reminder_push_candidates(TIMESTAMPTZ)
        TO reminder_worker;
    GRANT EXECUTE ON FUNCTION public.reminders_unsubscribe(UUID) TO anon, authenticated;

    REVOKE ALL ON TABLE public.user_notes, public.note_reviews, public.review_items, public.review_attempts,
        public.reminder_preferences, public.reminder_sends, public.push_subscriptions, public.product_events,
        public.import_items, public.learning_settings FROM PUBLIC, anon, authenticated;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_notes, public.note_reviews, public.review_items,
        public.reminder_preferences, public.import_items TO authenticated;
    GRANT SELECT, INSERT, DELETE ON TABLE public.review_attempts, public.push_subscriptions TO authenticated;
    GRANT SELECT, INSERT, UPDATE ON TABLE public.learning_settings TO authenticated;
    GRANT SELECT ON TABLE public.reminder_sends TO authenticated;
    GRANT INSERT ON TABLE public.product_events TO authenticated;

    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF has_function_privilege(r, 'public.reminder_candidates(timestamptz)', 'EXECUTE')
           OR has_function_privilege(r, 'public.reminder_push_candidates(timestamptz)', 'EXECUTE') THEN
            RAISE EXCEPTION '21 ABORTED: % can still list reminder candidates', r;
        END IF;
    END LOOP;
    FOREACH t IN ARRAY ARRAY['user_notes','note_reviews','review_items','review_attempts','reminder_preferences',
                             'reminder_sends','push_subscriptions','product_events','import_items','learning_settings'] LOOP
        IF has_table_privilege('anon', 'public.' || t, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE') THEN
            RAISE EXCEPTION '21 ABORTED: anon still has rights on %', t;
        END IF;
        IF has_table_privilege('authenticated', 'public.' || t, 'TRUNCATE') THEN
            RAISE EXCEPTION '21 ABORTED: authenticated can truncate %', t;
        END IF;
    END LOOP;
    IF NOT has_function_privilege('anon', 'public.reminders_unsubscribe(uuid)', 'EXECUTE')
       OR NOT has_function_privilege('authenticated', 'public.push_subscribe(text,text,text)', 'EXECUTE')
       OR NOT has_table_privilege('authenticated', 'public.user_notes', 'INSERT')
       OR has_table_privilege('authenticated', 'public.product_events', 'SELECT') THEN
        RAISE EXCEPTION '21 ABORTED: a right the app needs is missing, or events became readable';
    END IF;
    RAISE NOTICE '21 OK';
END $$;

-- ===== verification (fails -> everything above is undone) =====
DO $$
DECLARE t TEXT;
BEGIN
    IF current_setting('libris.rows_before') IS DISTINCT FROM concat_ws(',', (SELECT count(*) FROM public.books),
        (SELECT count(*) FROM public.favorites), (SELECT count(*) FROM public.user_activities),
        (SELECT count(*) FROM public.user_interactions)) THEN
        RAISE EXCEPTION 'an existing row count changed';
    END IF;
    FOREACH t IN ARRAY ARRAY['user_notes','note_reviews','review_items','review_attempts','reminder_preferences',
                             'reminder_sends','push_subscriptions','product_events','import_items','learning_settings'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = t AND rowsecurity) THEN
            RAISE EXCEPTION '% is missing or has no row-level security', t;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = t) THEN
            RAISE EXCEPTION '% has no policy', t;
        END IF;
    END LOOP;
    RAISE NOTICE 'ROLLOUT OK';
END $$;
NOTIFY pgrst, 'reload schema';
COMMIT;
