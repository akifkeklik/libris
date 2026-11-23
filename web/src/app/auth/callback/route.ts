import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@/lib/supabase/server';
import { sanitizeRedirect } from '@/lib/safeRedirect';

/**
 * Landing point for Supabase e-mail links (password reset) and OAuth sign-in: exchanges the
 * one-time `code` for a session cookie, then continues to `next` (same-site paths only).
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get('code');
  const next = sanitizeRedirect(searchParams.get('next'));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, origin));
    console.warn('[auth/callback] code exchange failed:', error.name);
  }
  const fail = new URL('/login', origin);
  fail.searchParams.set('error', 'link_invalid');
  return NextResponse.redirect(fail);
}
