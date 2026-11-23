'use client';

import { Suspense, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { sanitizeRedirect } from '@/lib/safeRedirect';
import { usePreferences } from '@/components/PreferencesProvider';
import { OAuthButtons } from '@/components/OAuthButtons';
import { LegalLinks } from '@/components/LegalLinks';
import { RememberMe } from '@/components/RememberMe';
import { isExistingAccount } from '@/lib/authErrors';
import { LOGIN_EMAIL_HANDOFF, setRememberChoice } from '@/lib/supabase/remember';


function SignUpForm() {
  const { t } = usePreferences();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmationSent, setConfirmationSent] = useState(false);
  const [existing, setExisting] = useState(false);
  const [remember, setRemember] = useState(true);
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = createClient();

  const rawRedirect = searchParams.get('redirect');
  const safeRedirect = rawRedirect ? sanitizeRedirect(rawRedirect) : '/?onboarding=true';
  const loginHref = rawRedirect ? `/login?redirect=${encodeURIComponent(rawRedirect)}` : '/login';

  const goToLogin = () => {
    try {
      sessionStorage.setItem(LOGIN_EMAIL_HANDOFF, email.trim());
    } catch {
      // Storage blocked: the log-in page simply opens empty.
    }
    router.push(loginHref);
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setExisting(false);
    setLoading(true);

    try {
      setRememberChoice(remember);
      const { data, error: authError } = await supabase.auth.signUp({
        email,
        password,
      });

      if (authError) {
        if (isExistingAccount(authError)) {
          setExisting(true);
          return;
        }
        throw authError;
      }

      if (data.session) {
        // Direct session created (auto-confirmed or confirmation disabled)
        router.push(safeRedirect);
        router.refresh();
      } else if (data.user) {
        // Supabase returns an empty identities array if email already exists with confirmation enabled
        if (isExistingAccount(null, data.user.identities)) {
          setExisting(true);
          return;
        }
        setConfirmationSent(true);
      }
    } catch (err: unknown) {
      console.warn('[signup]', err);
      setError(t('signup_error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel animate-fade-in" style={{ width: '100%', maxWidth: '400px', padding: '2.5rem' }}>
      <h1 style={{ fontSize: '2rem', textAlign: 'center', marginBottom: '0.5rem' }}>{t('signup_title')}</h1>
      <p className="text-muted text-center" style={{ marginBottom: '2rem' }}>{t('signup_subtitle')}</p>
      
      {error && (
        <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      {existing ? (
        <div role="status" data-testid="signup-existing" className="text-center" style={{ padding: '0.5rem 0' }}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>{t('signup_exists_title')}</h2>
          <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.9rem', lineHeight: 1.6, overflowWrap: 'anywhere' }}>
            {t('signup_exists_body', { email: email.trim() })}
          </p>
          <button type="button" onClick={goToLogin} className="btn btn-primary" style={{ width: '100%', padding: '0.9rem' }} data-testid="signup-existing-login">
            {t('nav_login')}
          </button>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1.25rem', marginTop: '1rem', fontSize: '0.85rem', flexWrap: 'wrap' }}>
            <Link href="/forgot-password" style={{ color: 'var(--primary-strong)' }}>{t('forgot_password_link')}</Link>
            <button type="button" onClick={() => setExisting(false)} style={{ color: 'var(--primary-strong)', textDecoration: 'underline', padding: 0, border: 0, cursor: 'pointer', font: 'inherit' }}>
              {t('signup_use_other_email')}
            </button>
          </div>
        </div>
      ) : confirmationSent ? (
        <div className="text-center" style={{ padding: '1rem 0' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✉️</div>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>{t('signup_check_email')}</h2>
          <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.875rem' }}>
            {t('signup_confirm_sent', { email })}
          </p>
          <Link
            href={rawRedirect ? `/login?redirect=${encodeURIComponent(rawRedirect)}` : '/login'}
            className="btn btn-primary"
            style={{ display: 'inline-block', width: '100%', padding: '0.75rem', textAlign: 'center' }}
          >
            {t('go_to_login')}
          </Link>
        </div>
      ) : (
        <>
        <form onSubmit={handleSignUp}>
          <div className="input-group">
            <label className="input-label" htmlFor="email">{t('email_label')}</label>
            <input 
              id="email"
              type="email"
              autoComplete="email"
              required 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              placeholder={t('email_placeholder')}
            />
          </div>
          
          <div className="input-group">
            <label className="input-label" htmlFor="password">{t('password_label')}</label>
            <input 
              id="password"
              type="password"
              autoComplete="new-password"
              required 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              placeholder={t('password_min_hint')}
              minLength={6}
            />
          </div>

          <RememberMe checked={remember} onChange={setRemember} />

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ width: '100%', marginTop: '1rem', padding: '1rem' }}
            disabled={loading}
          >
            {loading ? t('signup_button_loading') : t('signup_button')}
          </button>
        </form>
        <OAuthButtons redirect={safeRedirect} remember={remember} />
        <LegalLinks intro={t('signup_legal_notice')} />
        </>
      )}
      
      <p className="text-center" style={{ marginTop: '2rem', fontSize: '0.875rem' }}>
        {t('signup_have_account')}{' '}
        <Link
          href={loginHref}
          style={{ color: 'var(--primary-strong)', fontWeight: 500 }}
        >
          {t('nav_login')}
        </Link>
      </p>
    </div>
  );
}

export default function SignUpPage() {
  const { t } = usePreferences();
  return (
    <div className="container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '70vh' }}>
      <Suspense fallback={<div className="glass-panel" style={{ width: '100%', maxWidth: '400px', padding: '2.5rem', textAlign: 'center' }}>{t('loading')}</div>}>
        <SignUpForm />
      </Suspense>
    </div>
  );
}
