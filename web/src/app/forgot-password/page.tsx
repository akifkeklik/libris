'use client';

import { useState } from 'react';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';
import { usePreferences } from '@/components/PreferencesProvider';

/**
 * Requests a password-reset e-mail. The same confirmation is shown whether or not the address
 * has an account (and on errors), so the form cannot be used to find out who is registered.
 */
export default function ForgotPasswordPage() {
  const { t } = usePreferences();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const redirectTo = `${window.location.origin}/auth/callback?next=/reset-password`;
      const { error } = await createClient().auth.resetPasswordForEmail(email.trim(), { redirectTo });
      if (error) console.warn('[forgot-password]', error.name);
    } catch (err) {
      console.warn('[forgot-password]', err);
    } finally {
      setLoading(false);
      setSent(true);
    }
  };

  return (
    <div className="container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '70vh' }}>
      <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '400px', padding: '2.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', textAlign: 'center', marginBottom: '0.5rem' }}>{t('forgot_password_title')}</h1>
        {sent ? (
          <p role="status" data-testid="forgot-password-sent" style={{ textAlign: 'center', lineHeight: 1.6 }}>
            {t('forgot_password_sent')}
          </p>
        ) : (
          <>
            <p className="text-muted text-center" style={{ marginBottom: '2rem' }}>{t('forgot_password_subtitle')}</p>
            <form onSubmit={submit}>
              <div className="input-group">
                <label className="input-label" htmlFor="email">{t('email_label')}</label>
                <input id="email" type="email" required autoComplete="email" value={email}
                  onChange={(e) => setEmail(e.target.value)} className="input-field" placeholder={t('email_placeholder')} />
              </div>
              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem', padding: '1rem' }} disabled={loading}>
                {loading ? t('loading') : t('forgot_password_submit')}
              </button>
            </form>
          </>
        )}
        <p className="text-center" style={{ marginTop: '2rem', fontSize: '0.875rem' }}>
          <Link href="/login" style={{ color: 'var(--primary)', fontWeight: 500 }}>{t('back_to_login')}</Link>
        </p>
      </div>
    </div>
  );
}
