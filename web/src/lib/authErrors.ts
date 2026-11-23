/** Supabase reports an existing address either as an error (confirmations off) or, to avoid
 *  account enumeration, as a user without identities (confirmations on). */
export function isExistingAccount(err: unknown, identities?: unknown[] | null): boolean {
  if (Array.isArray(identities) && identities.length === 0) return true;
  const e = err as { code?: string; message?: string } | null;
  return !!e && (e.code === 'user_already_exists' || e.code === 'email_exists' || /already (been )?registered/i.test(e.message ?? ''));
}
