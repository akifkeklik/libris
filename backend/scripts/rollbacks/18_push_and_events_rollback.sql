-- Rollback for 18_push_and_events.sql. Drops push subscriptions (readers must allow notifications
-- again) and the product events. Readers whose channel is 'push' are moved back to e-mail (when an
-- address is known) so nobody silently loses their reminders.
BEGIN;
DROP FUNCTION IF EXISTS public.reminder_push_candidates(TIMESTAMPTZ);
DROP FUNCTION IF EXISTS public.push_subscribe(TEXT, TEXT, TEXT);
UPDATE public.reminder_preferences SET channel = 'email' WHERE channel = 'push' AND email IS NOT NULL;
DROP TABLE IF EXISTS public.push_subscriptions;
DROP TABLE IF EXISTS public.product_events;
COMMIT;
