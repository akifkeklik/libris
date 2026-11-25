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
