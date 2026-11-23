/**
 * "Remember me" for every sign-in (password, sign-up, Google).
 *
 * @supabase/ssr always writes the session cookies with a 400-day lifetime. When the reader unticks
 * "Remember me" we store a browser-session flag cookie (`libris-remember=0`, no expiry) and every
 * Supabase client — browser, server components/route handlers and the middleware that refreshes
 * the session — drops `maxAge`/`expires` from the auth cookies it writes. They then become session
 * cookies: closing the browser signs the reader out. Deletions (maxAge 0) are left untouched.
 */

export const REMEMBER_COOKIE = 'libris-remember';

type CookieOptions = { maxAge?: number; expires?: Date | number | string } & Record<string, unknown>;

export function isSessionOnly(flagValue: string | undefined | null): boolean {
  return flagValue === '0';
}

export function applyRemember<T extends CookieOptions | undefined>(options: T, sessionOnly: boolean): T {
  if (!sessionOnly || !options || options.maxAge === 0) return options;
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { maxAge, expires, ...rest } = options;
  return rest as T;
}

/** Called by the sign-in forms right before signing in. Browser only. */
export function setRememberChoice(remember: boolean): void {
  if (typeof document === 'undefined') return;
  const secure = typeof location !== 'undefined' && location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = remember
    ? `${REMEMBER_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax${secure}`
    : `${REMEMBER_COOKIE}=0; Path=/; SameSite=Lax${secure}`;
}

/** The address handed from the sign-up page to the log-in page (never put in the URL). */
export const LOGIN_EMAIL_HANDOFF = 'libris-login-email';
