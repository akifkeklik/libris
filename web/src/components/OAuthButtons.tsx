'use client';

import { useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { usePreferences } from '@/components/PreferencesProvider';
import { setRememberChoice } from '@/lib/supabase/remember';

/**
 * "Continue with Google". Hidden until NEXT_PUBLIC_AUTH_GOOGLE_ENABLED=true, because before the
 * Google provider is configured in Supabase the button would only lead to a Supabase error page.
 * The provider returns to /auth/callback, which opens the session and continues to `redirect`.
 */
export const GOOGLE_AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_GOOGLE_ENABLED === 'true';

export function OAuthButtons({ redirect, remember = true }: { redirect: string; remember?: boolean }) {
  const { t } = usePreferences();
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!GOOGLE_AUTH_ENABLED) return null;

  const signIn = async () => {
    setError(false);
    setLoading(true);
    setRememberChoice(remember);
    const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(redirect)}`;
    const { error: oauthError } = await createClient().auth.signInWithOAuth({ provider: 'google', options: { redirectTo } });
    if (oauthError) {
      console.warn('[oauth]', oauthError.name);
      setError(true);
      setLoading(false);
    }
    // On success the browser is already navigating to Google.
  };

  return (
    <div data-testid="oauth-buttons" style={{ marginTop: '1.5rem' }}>
      <div aria-hidden="true" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: '0 0 1rem', color: 'var(--text-muted-strong)', fontSize: '0.8rem' }}>
        <span style={{ flex: 1, height: 1, background: 'var(--card-border)' }} />
        {t('auth_or')}
        <span style={{ flex: 1, height: 1, background: 'var(--card-border)' }} />
      </div>
      {error && (
        <div role="alert" style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.875rem' }}>
          {t('oauth_failed')}
        </div>
      )}
      <button type="button" onClick={signIn} disabled={loading} className="btn btn-outline"
        style={{ width: '100%', padding: '0.9rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.6rem' }}>
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 48 48">
          <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.6 13.3l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
          <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17z" />
          <path fill="#FBBC05" d="M10.5 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C.9 16.6 0 20.2 0 24s.9 7.4 2.6 10.7l7.9-6.1z" />
          <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-2.1 1.4-4.8 2.2-8.5 2.2-6.3 0-11.6-4.1-13.5-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z" />
        </svg>
        {loading ? t('loading') : t('continue_with_google')}
      </button>
    </div>
  );
}
