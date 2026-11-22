'use client';

import { usePreferences } from '@/components/PreferencesProvider';

/**
 * "Remember me" switch shown on every sign-in form. Ticked (the default): the session survives
 * closing the browser. Unticked: the reader is signed out when the browser closes
 * (see lib/supabase/remember.ts).
 */
export function RememberMe({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  const { t } = usePreferences();
  return (
    <label className="remember-me" data-testid="remember-me">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="remember-me__box" aria-hidden="true">
        <svg viewBox="0 0 16 16" width="12" height="12"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
      <span className="remember-me__text">
        <span>{t('remember_me')}</span>
        <span className="remember-me__hint">{t(checked ? 'remember_me_on_hint' : 'remember_me_off_hint')}</span>
      </span>
    </label>
  );
}
