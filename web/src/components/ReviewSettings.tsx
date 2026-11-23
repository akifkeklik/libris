'use client';

import { useEffect, useState } from 'react';
import { Download, GraduationCap } from 'lucide-react';
import { usePreferences } from '@/components/PreferencesProvider';
import { exportAnkiAction, getLearningSettingsAction, saveLearningSettingsAction } from '@/app/actions/learning';

/**
 * Review settings: the FSRS target retention (only when the server runs FSRS) and the Anki export.
 * Retention: how sure the reader wants to be to still remember a card when it comes back.
 * Higher = more reviews, lower = fewer reviews and more forgetting.
 */
export function ReviewSettings() {
  const { t } = usePreferences();
  const [fsrs, setFsrs] = useState(false);
  const [retention, setRetention] = useState(90);
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'failed'>('idle');
  const [exporting, setExporting] = useState<'idle' | 'busy' | 'failed'>('idle');

  useEffect(() => {
    getLearningSettingsAction().then((s) => {
      if (!s) return;
      setFsrs(s.fsrs_enabled);
      setRetention(Math.round(s.desired_retention * 100));
    });
  }, []);

  const save = async () => {
    setStatus('saving');
    setStatus((await saveLearningSettingsAction(retention / 100)) ? 'saved' : 'failed');
  };

  const exportAnki = async () => {
    setExporting('busy');
    const res = await exportAnkiAction();
    if (!res.ok || !res.base64) {
      setExporting('failed');
      return;
    }
    const bytes = Uint8Array.from(atob(res.base64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
    const link = Object.assign(document.createElement('a'), { href: url, download: 'libris-cards.apkg' });
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setExporting('idle');
  };

  return (
    <section id="review-settings" className="glass-panel" style={{ padding: '2rem' }} data-testid="review-settings">
      <h2 style={{ fontSize: '1.4rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <GraduationCap size={20} color="var(--primary)" aria-hidden="true" />
        <span>{t('review_settings_title')}</span>
      </h2>

      {fsrs && (
        <div style={{ marginBottom: '1.75rem' }}>
          <label className="input-label" htmlFor="retention" style={{ display: 'block', marginBottom: '0.5rem' }}>{t('review_retention_label', { value: retention })}</label>
          <input id="retention" type="range" min={80} max={95} step={1} value={retention}
            onChange={(e) => { setRetention(Number(e.target.value)); setStatus('idle'); }}
            aria-valuetext={`${retention}%`} style={{ width: '100%', maxWidth: '28rem', accentColor: 'var(--primary)' }} />
          <p className="text-muted" style={{ fontSize: '0.85rem', lineHeight: 1.6, margin: '0.4rem 0 0.9rem' }}>{t('review_retention_help')}</p>
          <button type="button" className="btn btn-primary" disabled={status === 'saving'} onClick={save}>{t('review_retention_save')}</button>
          <span role="status" aria-live="polite" style={{ marginLeft: '0.75rem', fontSize: '0.875rem' }}>
            {status === 'saved' && t('review_retention_saved')}
            {status === 'failed' && <span style={{ color: 'var(--danger)' }}>{t('card_action_failed')}</span>}
          </span>
        </div>
      )}

      <div>
        <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{t('anki_export_title')}</p>
        <p className="text-muted" style={{ fontSize: '0.85rem', lineHeight: 1.6, margin: '0 0 0.9rem' }}>{t('anki_export_body')}</p>
        <button type="button" className="btn btn-outline" disabled={exporting === 'busy'} onClick={exportAnki}
          style={{ display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }} data-testid="anki-export">
          <Download size={16} aria-hidden="true" /> {exporting === 'busy' ? t('loading') : t('anki_export_button')}
        </button>
        {exporting === 'failed' && <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.875rem', marginTop: '0.5rem' }}>{t('card_action_failed')}</p>}
      </div>
    </section>
  );
}
