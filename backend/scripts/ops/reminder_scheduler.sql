-- Hourly trigger for the "Review Reminders" workflow, from Supabase (free: pg_cron + pg_net).
-- NOT a numbered migration: it needs a token and is applied once, by hand, by the owner.
--
-- Why: GitHub's own schedule ran this hourly job 4 times in about 31 hours (PHASE_3_REPORT.md).
-- Why not a backend endpoint: no public trigger to protect, and Render is not woken every hour.
--
-- Before: create a fine-grained GitHub token for this repository only, permission "Actions: write",
-- with an expiry date. Store it in Vault (never in this file):
--     select vault.create_secret('<token>', 'github_reminder_token');
-- Stop:   select cron.unschedule('libris-review-reminders');
-- Check:  select status, return_message, start_time from cron.job_run_details order by start_time desc limit 5;
--         select status_code, error_msg, created from net._http_response order by created desc limit 5;  -- expect 204

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM vault.decrypted_secrets WHERE name = 'github_reminder_token') THEN
        RAISE EXCEPTION 'store the GitHub token in Vault first (see the top of this file)';
    END IF;
END $$;

-- cron.schedule with a name replaces an existing job of that name, so this file can be re-run.
SELECT cron.schedule('libris-review-reminders', '7 * * * *', $job$
    SELECT net.http_post(
        url     := 'https://api.github.com/repos/akifkeklik/libris/actions/workflows/reminders.yml/dispatches',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'github_reminder_token'),
            'Accept', 'application/vnd.github+json', 'User-Agent', 'libris-reminders'),
        body    := '{"ref": "main", "inputs": {"dry_run": "false"}}'::jsonb,
        timeout_milliseconds := 10000)
    WHERE EXISTS (SELECT 1 FROM public.reminder_preferences WHERE channel <> 'off');
$job$);
