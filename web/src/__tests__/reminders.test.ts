import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ApiService } from '../lib/api';

const read = (...p: string[]) => readFileSync(join(__dirname, '..', ...p), 'utf8');

test('reminder settings start from the approved defaults and only take effect when saved', () => {
  const src = read('components', 'ReminderSettings.tsx');
  assert.match(src, /useState<'email' \| 'push' \| 'off'>\('email'\)/);
  assert.match(src, /useState\('09:00'\)/);
  assert.match(src, /resolvedOptions\(\)\.timeZone/, 'default time zone is the browser\'s');
  assert.match(src, /language: preferences\.language/, 'e-mails follow the UI language');
  assert.match(src, /reminders_not_saved/);
  assert.match(src, /\{pushKey && \(/, 'push is offered only when the server has a VAPID key');
  assert.match(src, /reminders_push_ios_hint/);
  assert.match(read('app', 'settings', 'page.tsx'), /\{user && <ReminderSettings \/>\}/);
});

test('saving reminder preferences is an uncached PUT of the validated fields', async () => {
  const realFetch = globalThis.fetch;
  let seen: { url: string; init: RequestInit } | null = null;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    seen = { url: String(url), init };
    return new Response('{}', { status: 200 });
  }) as typeof fetch;
  try {
    const res = await ApiService.saveReminderPreferences({ channel: 'email', local_time: '07:30', timezone: 'Europe/Istanbul', quiet_days: [0], language: 'tr' });
    assert.deepEqual(res, { ok: true, status: 200 });
  } finally {
    globalThis.fetch = realFetch;
  }
  const { url, init } = seen as unknown as { url: string; init: RequestInit };
  assert.match(url, /\/api\/reminders\/preferences$/);
  assert.equal(init.method, 'PUT');
  assert.equal(init.cache, 'no-store');
  assert.deepEqual(JSON.parse(String(init.body)), { channel: 'email', local_time: '07:30', timezone: 'Europe/Istanbul', quiet_days: [0], language: 'tr' });
});

test('the unsubscribe landing page is translated and links back to the settings section', () => {
  const src = read('app', 'reminders', 'unsubscribed', 'page.tsx');
  assert.match(src, /unsubscribed_title/);
  assert.match(src, /unsubscribed_invalid_title/);
  assert.match(src, /href="\/settings#reminders"/);
});

test('push: permission is asked from the save click, iOS needs the Home Screen, payload opens our origin only', async () => {
  const src = read('components', 'ReminderSettings.tsx');
  assert.ok(src.indexOf('subscribeToPush(pushKey)') > src.indexOf('const save = async'), 'subscription happens inside save');
  assert.match(src, /savedChannel === 'push'[\s\S]*unsubscribeFromPush/, 'leaving push removes this device');
  const push = read('lib', 'push.ts');
  assert.match(push, /isIos\(\) && !isStandalone\(\)\) return 'ios-needs-install'/);
  assert.match(push, /userVisibleOnly: true/);
  const sw = readFileSync(join(__dirname, '..', '..', 'public', 'sw.js'), 'utf8');
  assert.match(sw, /addEventListener\('push'/);
  assert.match(sw, /target\.origin === self\.location\.origin/);
  const manifest = JSON.parse(readFileSync(join(__dirname, '..', '..', 'public', 'manifest.json'), 'utf8'));
  assert.ok(manifest.icons.some((i: { sizes: string }) => i.sizes === '512x512'), 'installable icon');
  const { urlBase64ToUint8Array } = await import('../lib/push');
  assert.deepEqual(Array.from(urlBase64ToUint8Array('AQID_-8')), [1, 2, 3, 255, 239]);
});

test('product events: reminder_opened once per reminder, review_session_completed when the queue is cleared', () => {
  const page = read('app', 'learning', 'page.tsx');
  assert.match(page, /event: 'reminder_opened'/);
  assert.match(page, /sessionStorage\.setItem\(key, '1'\)/);
  const dash = read('components', 'LearningDashboard.tsx');
  assert.match(dash, /event: 'review_session_completed', props: \{ reviewed_count:/);
});
