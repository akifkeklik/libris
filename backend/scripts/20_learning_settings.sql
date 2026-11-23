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
