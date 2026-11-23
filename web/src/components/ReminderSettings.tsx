'use client';

import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import { usePreferences } from '@/components/PreferencesProvider';
import {
  deletePushSubscriptionAction,
  getPushPublicKeyAction,
  getReminderPreferencesAction,
  savePushSubscriptionAction,
  saveReminderPreferencesAction,
} from '@/app/actions/reminders';
import { pushSupport, subscribeToPush, unsubscribeFromPush, type PushSupport } from '@/lib/push';
import type { TranslationKey } from '@/lib/i18n';

const WEEKDAYS: TranslationKey[] = ['day_sun', 'day_mon', 'day_tue', 'day_wed', 'day_thu', 'day_fri', 'day_sat'];

let zoneCache: string[] | null = null;
/** IANA zones the browser knows, computed once (for the time zone suggestions). */
function supportedZones(): string[] {
  if (zoneCache) return zoneCache;
  try {
    zoneCache = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.('timeZone') ?? [];
  } catch {
    zoneCache = [];
  }
  return zoneCache;
}

function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/**
 * Daily review reminder settings. Defaults (approved by the owner): e-mail, 09:00, the browser's
 * time zone, no quiet days. Push appears once the server has a VAPID key; on iPhone/iPad it needs
 * Libris on the Home Screen first, which the section explains. Nothing is sent until the reader saves; the e-mail goes to the
 * address of the signed-in account.
 */
export function ReminderSettings() {
  const { t, preferences } = usePreferences();
  const [channel, setChannel] = useState<'email' | 'push' | 'off'>('email');
  const [savedChannel, setSavedChannel] = useState<'email' | 'push' | 'off' | null>(null);
  const [pushKey, setPushKey] = useState<string | null>(null);
  const [support, setSupport] = useState<PushSupport>('unsupported');
  const [time, setTime] = useState('09:00');
  const [tz, setTz] = useState('UTC');
  const [quiet, setQuiet] = useState<number[]>([]);
  const [saved, setSaved] = useState<boolean | null>(null);
  const [status, setStatus] = useState<'idle' | 'saving' | 'ok' | 'invalid' | 'unavailable' | 'push_denied'>('idle');
  const [zones, setZones] = useState<string[]>([]);

  useEffect(() => {
    // Browser-only values are set after loading, not during render (the server's zone differs).
    getPushPublicKeyAction().then((key) => {
      setPushKey(key);
      setSupport(pushSupport());
    });
    getReminderPreferencesAction().then((p) => {
      setZones(supportedZones());
      if (!p || !p.saved) {
        setTz(browserTimeZone());
        setSaved(false);
        return;
      }
      setSaved(true);
      setChannel(p.channel);
      setSavedChannel(p.channel);
      setTime(p.local_time);
      setTz(p.timezone);
      setQuiet(p.quiet_days ?? []);
    });
  }, []);

  const save = async () => {
    setStatus('saving');
    if (channel === 'push') {
      // Permission prompt must come straight from this click.
      const sub = pushKey ? await subscribeToPush(pushKey) : null;
      if (sub === 'denied') {
        setSupport(pushSupport());
        setStatus('push_denied');
        return;
      }
      if (!sub || !(await savePushSubscriptionAction(sub))) {
        setStatus('unavailable');
        return;
      }
    } else if (savedChannel === 'push') {
      const endpoint = await unsubscribeFromPush();
      if (endpoint) await deletePushSubscriptionAction(endpoint);
    }
    const res = await saveReminderPreferencesAction({
      channel, local_time: time, timezone: tz, quiet_days: quiet, language: preferences.language,
    });
    if (res.ok) {
      setSaved(true);
      setSavedChannel(channel);
      setStatus('ok');
    } else {
      setStatus(res.reason ?? 'unavailable');
    }
  };

  const pushReady = !!pushKey && support === 'supported';

  const toggleDay = (d: number) => setQuiet((q) => (q.includes(d) ? q.filter((x) => x !== d) : [...q, d].sort()));

  return (
    <section id="reminders" className="glass-panel" style={{ padding: '2rem' }} data-testid="reminder-settings">
      <h2 style={{ fontSize: '1.4rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <Bell size={20} color="var(--primary)" aria-hidden="true" />
        <span>{t('reminders_title')}</span>
      </h2>
      <p className="text-muted" style={{ fontSize: '0.9rem', lineHeight: 1.6, margin: '0 0 1.25rem' }}>{t('reminders_body')}</p>
      {saved === false && (
        <p role="note" style={{ fontSize: '0.85rem', margin: '0 0 1rem', color: 'var(--text-muted-strong)' }}>{t('reminders_not_saved')}</p>
      )}

      <fieldset style={{ border: 0, padding: 0, margin: '0 0 1rem' }}>
        <legend className="input-label">{t('reminders_channel')}</legend>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <label><input type="radio" name="reminder-channel" checked={channel === 'email'} onChange={() => setChannel('email')} /> {t('reminders_channel_email')}</label>
          <label><input type="radio" name="reminder-channel" checked={channel === 'off'} onChange={() => setChannel('off')} /> {t('reminders_channel_off')}</label>
          {pushKey && (
            <label className={pushReady ? undefined : 'text-muted'}>
              <input type="radio" name="reminder-channel" checked={channel === 'push'} disabled={!pushReady}
                onChange={() => setChannel('push')} data-testid="reminder-channel-push" /> {t('reminders_channel_push')}
            </label>
          )}
        </div>
        {pushKey && support !== 'supported' && (
          <p role="note" data-testid="push-hint" style={{ fontSize: '0.82rem', margin: '0.6rem 0 0', color: 'var(--text-muted-strong)', lineHeight: 1.5 }}>
            {t(support === 'ios-needs-install' ? 'reminders_push_ios_hint' : support === 'denied' ? 'reminders_push_denied' : 'reminders_push_unsupported')}
          </p>
        )}
      </fieldset>

      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <div className="input-group" style={{ minWidth: '8rem' }}>
          <label className="input-label" htmlFor="reminder-time">{t('reminders_time')}</label>
          <input id="reminder-time" type="time" className="input-field" value={time} step={900}
            onChange={(e) => setTime(e.target.value.slice(0, 5))} disabled={channel === 'off'} />
        </div>
        <div className="input-group" style={{ flex: 1, minWidth: '12rem' }}>
          <label className="input-label" htmlFor="reminder-tz">{t('reminders_timezone')}</label>
          <input id="reminder-tz" className="input-field" value={tz} list="reminder-tz-list"
            onChange={(e) => setTz(e.target.value)} disabled={channel === 'off'} />
          <datalist id="reminder-tz-list">{zones.map((z) => <option key={z} value={z} />)}</datalist>
        </div>
      </div>

      <fieldset style={{ border: 0, padding: 0, margin: '0.5rem 0 1.25rem' }} disabled={channel === 'off'}>
        <legend className="input-label">{t('reminders_quiet_days')}</legend>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {WEEKDAYS.map((key, d) => (
            <label key={key} className="filter-chip" style={{ padding: '0.3rem 0.7rem' }}>
              <input type="checkbox" checked={quiet.includes(d)} onChange={() => toggleDay(d)} /> {t(key)}
            </label>
          ))}
        </div>
      </fieldset>

      <button type="button" className="btn btn-primary" onClick={save} disabled={status === 'saving'}>
        {status === 'saving' ? t('loading') : t('reminders_save')}
      </button>
      <p role="status" aria-live="polite" style={{ fontSize: '0.875rem', marginTop: '0.75rem' }}>
        {status === 'ok' && t(channel === 'off' ? 'reminders_saved_off' : channel === 'push' ? 'reminders_saved_push' : 'reminders_saved_on', { time, tz })}
        {status === 'push_denied' && <span style={{ color: 'var(--danger)' }}>{t('reminders_push_denied')}</span>}
        {status === 'invalid' && <span style={{ color: 'var(--danger)' }}>{t('reminders_invalid')}</span>}
        {status === 'unavailable' && <span style={{ color: 'var(--danger)' }}>{t('reminders_unavailable')}</span>}
      </p>
    </section>
  );
}
