# Faz 3 — Reminder loop (report)

Branch `feat/phase-3-reminders`, PR #101. Goal: bring readers back to their due questions at the
right time — once a day at most, at the reader's own hour, in their language, by e-mail or by
notification, with a one-click way out.

## What changed

| Area | Change |
| --- | --- |
| Database (17) | `reminder_preferences` (channel email/push/off, local time, IANA time zone, quiet days, language, e-mail from the session, unsubscribe token), `reminder_sends` (one row per reader, local date and channel → the daily send is idempotent). Time zone validated against `pg_timezone_names`. `reminder_candidates(now)` returns readers whose local hour has come, with due questions, not on a quiet day and not yet sent today. `reminders_unsubscribe(token)` for the link. Least-privilege role `reminder_worker` (NOLOGIN until the operator enables it): only the candidate function and the send log. |
| Database (18) | `push_subscriptions` (RLS: own rows; worker may read and delete → 404/410 cleanup), `push_subscribe()` (an endpoint follows the account currently signed in on that browser; max 10 devices per reader), `reminder_push_candidates(now)`, `product_events` (insert-only for readers, whitelisted events, ≤512-byte props, nobody can read them through the API). |
| Backend | `GET/PUT /api/reminders/preferences`, public `GET/POST /api/reminders/unsubscribe` (RFC 8058 one-click), `GET /api/reminders/push-key`, `POST/DELETE /api/reminders/push-subscription`, `POST /api/events`. E-mail behind `EmailPort` (Resend adapter + fake), push behind `WebPushAdapter` (pywebpush, VAPID, aes128gcm) + fake. E-mails and notifications in the reader's language (6). |
| Worker | `backend/scripts/send_reminders.py`, hourly via `.github/workflows/reminders.yml` (no public trigger, Render not woken). Claim (insert into `reminder_sends`) before sending; temporary provider errors release the claim so the next hour retries; permanent ones keep it (no hourly retry storm). Push goes to every device of the reader; gone devices are deleted. Each channel runs only when its secrets exist; with none the job exits 0. Logs counts only. |
| Web | Settings → "Daily review reminder" (channel, time, time zone with browser default, quiet days). Push option appears only when the server has a VAPID key; iPhone/iPad readers get the "Add to Home Screen" explanation (iOS only allows Web Push for installed web apps); blocked/unsupported browsers get a clear message. `/reminders/unsubscribed` landing page. Service worker shows the notification and opens only our own origin. Real PWA icons (192/512/maskable, apple-touch-icon) and `appleWebApp` metadata. |
| Events | `reminder_sent` = rows of `reminder_sends`; `reminder_opened` (learning page opened from a reminder link, once per reminder and tab); `review_session_completed` (the reader cleared every due question on that visit, with the count). |
| Privacy | Privacy policy gets a "Reminders" section in all 6 languages (what is stored, Resend and push services as processors, the two usage events, one-click unsubscribe). |

Also in this branch (asked for by the owner during Faz 3):

- **Remember me** on log-in, sign-up and Google sign-in. Unticked → auth cookies become browser-session cookies in all three Supabase clients (browser, server, middleware); deletions untouched.
- **Already registered e-mail on sign-up** → "You already have an account" panel with **Log in**; the log-in page opens with the address filled in (handed over in `sessionStorage`, never in the URL) and the cursor in the password field. Also links to "Forgot password" and "Use another e-mail".
- **Premium dropdown**: native `<select>` (unstyleable open list, clipped text in the dark theme) replaced everywhere by `components/Select.tsx` — WAI-ARIA select-only combobox, ↑/↓/Home/End/Enter/Esc/type-ahead, check mark on the chosen item, opens upwards near the bottom of the screen, reduced-motion aware. Used for library sort, shelf status, discovery shelf, reading goal type and the add-book genre.

## How it was tested

- `backend/tests/sql/test_17_reminders.sql`, `test_18_push_and_events.sql` — real PostgreSQL in CI (Migration Validation): candidates per time zone (Istanbul / New York), quiet days, off channel, no due items, same-day idempotency, next day, invalid zone, unsubscribe, RLS between readers, worker-role limits, anon, push endpoint ownership move, 10-device cap, https-only endpoints, event whitelist and insert-only, cascade on account deletion; migration 18 applied twice, rolled back and re-applied. Migration 17 checks passed in CI; 18 runs in the same step.
- Locally (pgserver): all migrations (except the pgvector ones) + 18 twice + rollback + re-forward apply cleanly. The local server has no time-zone database, so the runtime SQL checks run in CI only.
- `backend/tests/test_reminders.py` — 25 tests: validation, e-mail content and headers, push payload (count, never the question text), event whitelist, worker idempotency/retry/permanent failure, push fan-out, gone-device cleanup, temporary push failure releases the claim, endpoints require login, unsubscribe works without login, Resend adapter errors never contain the key.
- Real pywebpush 2.5.0 with a key pair from `generate_vapid_keys.py` (HTTP mocked): `Authorization: vapid …` carries our public key, body `aes128gcm`, 410 → subscription deleted.
- Web unit tests (all pass): reminder defaults, PUT shape, push flow order (permission inside the save click), iOS rule, SW opens only our origin, manifest icons, base64url decoding, events, remember-me cookie handling, existing-account detection, SSR safety of the browser Supabase client (regression test for a bug found during this phase — it fails on the earlier code).
- E2E core journeys 27/27; offline signed-in journey for dropdown, remember-me (auth cookies have no expiry) and the existing-account → prefilled log-in flow.

## Manual production steps (owner — nothing here was done to production)

1. Apply migrations **after** 09/10/13 are applied: `17_reminders.sql`, then `18_push_and_events.sql` (SQL editor, as `postgres`). Rollbacks: `scripts/rollbacks/18_…_rollback.sql`; 17 is dropped with `DROP TABLE reminder_sends, reminder_preferences; DROP FUNCTION reminder_candidates, reminders_unsubscribe;`.
2. Enable the worker role: `ALTER ROLE reminder_worker LOGIN PASSWORD '<strong password>';` → connection string with the **pooler** host as `REMINDER_DB_URL`.
3. Resend (free tier): verify the sending domain (SPF/DKIM), create an API key.
4. Web Push (optional): `python -m backend.scripts.generate_vapid_keys` on your machine. Public key → Render env `VAPID_PUBLIC_KEY`; private key → GitHub secret `VAPID_PRIVATE_KEY`; `VAPID_SUBJECT` = `mailto:<your address>`.
5. Render env: `APP_URL` (web address; the unsubscribe redirect needs it) and `VAPID_PUBLIC_KEY`.
6. GitHub → Settings → Secrets → Actions: `REMINDER_DB_URL`, `RESEND_API_KEY`, `REMINDER_FROM`, `APP_URL`, `API_URL`, (`VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`).
7. Run "Review Reminders" manually once with `dry_run = true`, read the counts, then let the hourly schedule run.

## Rollback

Disable the workflow (Actions → Review Reminders → Disable) — nothing is sent any more. Revert the
PR for the code. Database: the rollback scripts above (push readers are moved back to e-mail).

## Known limits / not done

- No in-app "send me a test notification" button; the dry run covers the e-mail side.
- `product_events` has no dashboard yet; query it in the SQL editor (`select event, count(*) … group by 1`).
- Quiet hours inside a day are not supported (one send time per day by design).
- GitHub scheduled workflows can start a few minutes late; reminders are "around" the chosen time.

## Finding after release: GitHub does not run the schedule hourly

Measured 2026-11-24 to 25: four scheduled runs (05:57, 17:33, 02:20, 12:42 UTC) instead of about 31,
9 to 12 hours apart. "A few minutes late" above was wrong. A 09:00 reminder could arrive in the evening,
and one set late in the day can miss its date. Do not enable reminders for readers until an external
scheduler (Supabase `pg_cron` + `pg_net`, or a free cron service calling `workflow_dispatch`) runs it hourly.
The send log keeps extra runs safe. `workflow_dispatch` defaults to a dry run, so pass `dry_run=false`.
