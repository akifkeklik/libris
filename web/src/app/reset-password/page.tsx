'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { usePreferences } from '@/components/PreferencesProvider';

const MIN_PASSWORD_LENGTH = 8;

/** Sets a new password. Reached from the reset e-mail via /auth/callback, which opens a session. */
export default function ResetPasswordPage() {
  const { t } = usePreferences();
  const router = useRouter();
  const [hasSession, setHasSession] = useState<boolean | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setHasSession(Boolean(data.user))).catch(() => setHasSession(false));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD_LENGTH) return setError(t('reset_password_too_short', { min: MIN_PASSWORD_LENGTH }));
    if (password !== confirm) return setError(t('reset_password_mismatch'));
    setLoading(true);
    const { error: updateError } = await createClient().auth.updateUser({ password });
    setLoading(false);
    if (updateError) {
      console.warn('[reset-password]', updateError.name);
      return setError(t('reset_password_failed'));
    }
    router.push('/catalog?password_updated=1');
    router.refresh();
  };

  return (
    <div className="container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '70vh' }}>
      <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '400px', padding: '2.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', textAlign: 'center', marginBottom: '1.5rem' }}>{t('reset_password_title')}</h1>
        {hasSession === false ? (
          <p role="alert" data-testid="reset-link-expired" style={{ textAlign: 'center', lineHeight: 1.6 }}>
            {t('reset_password_link_expired')}{' '}
            <Link href="/forgot-password" style={{ color: 'var(--primary)', fontWeight: 500 }}>{t('forgot_password_submit')}</Link>
          </p>
        ) : (
          <form onSubmit={submit}>
            {error && (
              <div role="alert" style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.875rem' }}>
                {error}
              </div>
            )}
            <div className="input-group">
              <label className="input-label" htmlFor="new-password">{t('reset_password_new')}</label>
              <input id="new-password" type="password" required autoComplete="new-password" minLength={MIN_PASSWORD_LENGTH}
                value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" />
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="confirm-password">{t('reset_password_confirm')}</label>
              <input id="confirm-password" type="password" required autoComplete="new-password" minLength={MIN_PASSWORD_LENGTH}
                value={confirm} onChange={(e) => setConfirm(e.target.value)} className="input-field" />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem', padding: '1rem' }}
              disabled={loading || hasSession === null}>
              {loading ? t('loading') : t('reset_password_submit')}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
