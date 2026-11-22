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
