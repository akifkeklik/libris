'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Trash2 } from 'lucide-react';
import { usePreferences } from '@/components/PreferencesProvider';
import { createClient } from '@/lib/supabase/client';
import { deleteAccountAction } from '@/app/actions/account';

/** Permanent account deletion with a typed confirmation (the reader's own e-mail address). */
export function DeleteAccountSection({ email }: { email: string }) {
  const { t } = usePreferences();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmed = typed.trim().toLowerCase() === email.trim().toLowerCase() && email.trim() !== '';

  const remove = async () => {
    setBusy(true);
    setError(null);
    const result = await deleteAccountAction();
    if (result.ok) {
      await createClient().auth.signOut().catch(() => undefined);
      router.push('/?account_deleted=1');
      router.refresh();
      return;
    }
    setBusy(false);
    setError(t(result.reason === 'unavailable' ? 'delete_account_unavailable' : 'delete_account_failed'));
  };

  return (
    <div data-testid="delete-account" style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--card-border)' }}>
      <h3 style={{ fontSize: '1.05rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
        <Trash2 size={18} aria-hidden="true" /> {t('delete_account_title')}
      </h3>
      <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: 1.6, margin: '0.5rem 0 1rem' }}>
        {t('delete_account_body')}
      </p>
      {!open ? (
        <button type="button" className="btn btn-outline" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
          onClick={() => setOpen(true)}>
          {t('delete_account_start')}
        </button>
      ) : (
        <div>
          <label className="input-label" htmlFor="delete-confirm-email">{t('delete_account_type_email')}</label>
          <input id="delete-confirm-email" type="email" autoComplete="off" className="input-field" value={typed}
            onChange={(e) => setTyped(e.target.value)} placeholder={email} />
          {error && <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.875rem', marginTop: '0.75rem' }}>{error}</p>}
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button type="button" className="btn btn-primary" disabled={!confirmed || busy} onClick={remove}
              style={{ background: 'var(--danger)', borderColor: 'var(--danger)' }}>
              {busy ? t('loading') : t('delete_account_confirm')}
            </button>
            <button type="button" className="btn btn-outline" disabled={busy}
              onClick={() => { setOpen(false); setTyped(''); setError(null); }}>
              {t('cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
