'use client';

import { useEffect, useState } from 'react';
import { Hourglass } from 'lucide-react';
import { usePreferences } from '@/components/PreferencesProvider';

/** How long a loading screen may stay silent before it explains the wait. */
export const SLOW_SERVER_NOTICE_DELAY_MS = 4000;

/**
 * Shown inside route loading screens. The backend sleeps when idle and its first request can
 * take up to a minute, so after a few seconds the skeleton says so instead of hanging silently.
 * Cached pages render before the delay elapses, so they never show it.
 */
export function SlowServerNotice({ delayMs = SLOW_SERVER_NOTICE_DELAY_MS }: { delayMs?: number }) {
  const { t } = usePreferences();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delayMs);
    return () => clearTimeout(timer);
  }, [delayMs]);

  return (
    <div role="status" aria-live="polite" data-testid="slow-server-notice">
      {visible && (
        <div
          className="glass-panel"
          style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start', padding: '1rem 1.25rem', marginBottom: '1.5rem' }}
        >
          <Hourglass size={20} aria-hidden="true" style={{ flexShrink: 0, marginTop: '0.15rem', color: 'var(--primary)' }} />
          <div>
            <p style={{ fontWeight: 600, margin: 0 }}>{t('server_waking_title')}</p>
            <p className="text-muted" style={{ margin: '0.25rem 0 0', fontSize: '0.9rem', lineHeight: 1.5 }}>
              {t('server_waking_body')}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
