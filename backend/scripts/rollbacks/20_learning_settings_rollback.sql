-- Rollback for 20_learning_settings.sql. Readers fall back to the default retention (0.90).
BEGIN;
DROP TABLE IF EXISTS public.learning_settings;
COMMIT;
