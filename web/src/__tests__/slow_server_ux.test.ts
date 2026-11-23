import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { LOCALES } from '../lib/i18n';
import { LANGUAGES } from '../lib/preferences';
import { SLOW_SERVER_NOTICE_DELAY_MS } from '../components/SlowServerNotice';

// The backend sleeps when idle and its first request can outlast the 10 s API timeout. Loading
// screens must explain the wait, and a timeout must not be blamed on the reader's connection.

const APP = join(__dirname, '..', 'app');
const read = (...parts: string[]) => readFileSync(join(APP, ...parts), 'utf8');

test('every route loading screen explains a slow (waking) server', () => {
  for (const file of [['loading.tsx'], ['catalog', 'loading.tsx'], ['book', '[isbn]', 'loading.tsx']]) {
    assert.match(read(...file), /<SlowServerNotice\b/, `${file.join('/')} has no SlowServerNotice`);
  }
});

test('the notice waits a few seconds, so cached pages never show it', () => {
  assert.ok(SLOW_SERVER_NOTICE_DELAY_MS >= 2000 && SLOW_SERVER_NOTICE_DELAY_MS <= 8000);
});

test('catalog and book pages use translated, honest service messages', () => {
  for (const file of [['catalog', 'page.tsx'], ['book', '[isbn]', 'page.tsx']]) {
    const src = read(...file);
    assert.doesNotMatch(src, /check your connection/i, `${file.join('/')} still blames the connection`);
    assert.match(src, /t\('service_timeout'\)|'service_timeout'/, `${file.join('/')} has no timeout message`);
  }
});

test('the waking-server texts exist in every language and differ from English outside en', () => {
  for (const lang of LANGUAGES) {
    for (const key of ['server_waking_title', 'server_waking_body', 'service_timeout', 'service_unavailable'] as const) {
      assert.ok(LOCALES[lang][key]?.trim(), `${lang}.${key} missing`);
      if (lang !== 'en') assert.notEqual(LOCALES[lang][key], LOCALES.en[key], `${lang}.${key} is untranslated`);
    }
  }
});
