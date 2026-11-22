import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ApiService } from '../lib/api';

const read = (...p: string[]) => readFileSync(join(__dirname, '..', ...p), 'utf8');

test('reminder settings start from the approved defaults and only take effect when saved', () => {
  const src = read('components', 'ReminderSettings.tsx');
  assert.match(src, /useState<'email' \| 'off'>\('email'\)/);
  assert.match(src, /useState\('09:00'\)/);
  assert.match(src, /resolvedOptions\(\)\.timeZone/, 'default time zone is the browser\'s');
  assert.match(src, /language: preferences\.language/, 'e-mails follow the UI language');
  assert.match(src, /reminders_not_saved/);
  assert.match(src, /reminders_channel_push_soon/);
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
