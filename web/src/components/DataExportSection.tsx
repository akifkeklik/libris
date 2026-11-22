'use client';

import { useState } from 'react';
import { Download } from 'lucide-react';
import { usePreferences } from '@/components/PreferencesProvider';
import { exportAccountAction } from '@/app/actions/account';

/** "Download my data": notes, review cards, review history, library and profile (JSON or Markdown). */
export function DataExportSection() {
  const { t } = usePreferences();
  const [busy, setBusy] = useState<'json' | 'markdown' | null>(null);
  const [error, setError] = useState(false);

  const download = async (format: 'json' | 'markdown') => {
    setBusy(format);
    setError(false);
    const result = await exportAccountAction(format);
    setBusy(null);
    if (!result.ok) return setError(true);
    const url = URL.createObjectURL(new Blob([result.content], { type: result.mimeType }));
    const link = Object.assign(document.createElement('a'), { href: url, download: result.filename });
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid="data-export" style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--card-border)' }}>
      <h3 style={{ fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
        <Download size={18} aria-hidden="true" /> {t('export_data_title')}
      </h3>
      <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: 1.6, margin: '0.5rem 0 1rem' }}>{t('export_data_body')}</p>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-outline" disabled={busy !== null} onClick={() => download('json')}>
          {busy === 'json' ? t('loading') : t('export_data_json')}
        </button>
        <button type="button" className="btn btn-outline" disabled={busy !== null} onClick={() => download('markdown')}>
          {busy === 'markdown' ? t('loading') : t('export_data_markdown')}
        </button>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.875rem', marginTop: '0.75rem' }}>{t('export_data_failed')}</p>}
    </div>
  );
}
