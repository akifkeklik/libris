-- Rollback for 16_account_deletion.sql: removes the self-service deletion RPC.
-- The ON DELETE CASCADE foreign keys are kept on purpose: NO ACTION made deleting a
-- user impossible (even from the Supabase dashboard), which is the bug 16 fixed.
BEGIN;
DROP FUNCTION IF EXISTS public.delete_my_account();
COMMIT;
