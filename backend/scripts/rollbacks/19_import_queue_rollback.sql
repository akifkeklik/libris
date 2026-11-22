-- Rollback for 19_import_queue.sql. Drops the approval queue. Notes and shelves that were
-- already approved are ordinary notes/library entries and stay.
BEGIN;
DROP TABLE IF EXISTS public.import_items;
DROP FUNCTION IF EXISTS public.import_items_cap();
COMMIT;
