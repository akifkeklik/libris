import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createTransport, type BaseTransportOptions } from '@sentry/core';
import * as Sentry from '@sentry/nextjs';
import { cleanText, scrubBreadcrumb, scrubSentryEvent, sentryOptions } from '../lib/sentryScrub';

// Notes, questions and e-mail addresses must never reach Sentry. Strings are built at runtime so
// that Sentry's source-context lines (which show this file's code) cannot contain them.
const NOTE = ['My', 'private', 'reading', 'note', 'about', 'grief'].join(' ');
const EMAIL = ['reader.private', 'example.com'].join('@');
const QUERY = ['grief', 'and', 'my', 'mother'].join('+');

test('scrubSentryEvent removes identity, request content and exception text', () => {
  const event = {
    user: { id: 'u1', email: EMAIL, ip_address: '1.2.3.4' },
    request: { method: 'POST', url: `https://libris/catalog?q=${QUERY}`, data: { content: NOTE },
               cookies: { sb: 'session' }, query_string: `q=${QUERY}`,
               headers: { Authorization: 'Bearer tok', 'User-Agent': 'ua', Cookie: 'sb=session' } },
    extra: { request_id: 'r1', note: NOTE },
    exception: { values: [{ type: 'TypeError', value: `cannot save ${NOTE} for ${EMAIL}`,
                            stacktrace: { frames: [{ vars: { note: NOTE } }] } }] },
    message: `failed for ${EMAIL}`,
  };
  const out = JSON.stringify(scrubSentryEvent(event));
  for (const leaked of [NOTE, EMAIL, QUERY, 'Bearer tok', 'sb=session', '1.2.3.4']) {
    assert.ok(!out.includes(leaked), `leaked: ${leaked}`);
  }
  assert.ok(out.includes('TypeError') && out.includes('[redacted]'));
  assert.deepEqual(event.request, { method: 'POST', url: 'https://libris/catalog', headers: { 'User-Agent': 'ua' } });
});

test('breadcrumbs: console and UI text dropped, request content removed, URLs without queries', () => {
  assert.equal(scrubBreadcrumb({ category: 'console', message: NOTE }), null);
  assert.equal(scrubBreadcrumb({ category: 'ui.input', message: NOTE }), null);
  const fetchCrumb = scrubBreadcrumb({ category: 'fetch', data: { url: `/api/search?q=${QUERY}`, method: 'GET',
                                                                  status_code: 200, request_body: NOTE } });
  assert.deepEqual(fetchCrumb, { category: 'fetch', data: { url: '/api/search', method: 'GET', status_code: 200 } });
  const nav = scrubBreadcrumb({ category: 'navigation', data: { from: `/catalog?q=${QUERY}`, to: '/book/1' } });
  assert.deepEqual(nav, { category: 'navigation', data: { from: '/catalog', to: '/book/1' } });
});

test('cleanText masks e-mails and truncates long text', () => {
  assert.equal(cleanText(`hi ${EMAIL}`), 'hi [email]');
  assert.ok(String(cleanText('x'.repeat(1000))).endsWith('[truncated]'));
});

test('the real Sentry SDK, configured as in production, sends no user data', async () => {
  const sent: string[] = [];
  Sentry.init({
    ...sentryOptions('https://public@o0.ingest.sentry.io/0'),
    transport: (options: BaseTransportOptions) => createTransport(options, async (req) => {
      sent.push(typeof req.body === 'string' ? req.body : new TextDecoder().decode(req.body as Uint8Array));
      return { statusCode: 200 };
    }),
  });
  Sentry.addBreadcrumb({ category: 'console', message: `typed note: ${NOTE}` });
  Sentry.addBreadcrumb({ category: 'fetch', data: { url: `/api/books?q=${QUERY}`, method: 'GET' } });
  Sentry.setUser({ id: 'u1', email: EMAIL });
  Sentry.captureException(new Error(`could not save ${NOTE} for ${EMAIL}`));
  await Sentry.flush(2000);
  await Sentry.close(2000);
  const payload = sent.join('\n');
  assert.ok(payload.includes('[redacted]'), 'the error must still be reported');
  for (const leaked of [NOTE, EMAIL, QUERY]) assert.ok(!payload.includes(leaked), `leaked to Sentry: ${leaked}`);
});

test('Sentry is opt-in: no DSN means no init, and the browser SDK is only loaded dynamically', () => {
  const client = readFileSync(join(__dirname, '..', 'instrumentation-client.ts'), 'utf8');
  const server = readFileSync(join(__dirname, '..', 'instrumentation.ts'), 'utf8');
  assert.match(client, /if \(dsn\)/);
  assert.doesNotMatch(client, /^import \* as Sentry|^import .* from '@sentry\/nextjs'/m, 'static import would ship the SDK to every reader');
  assert.match(server, /if \(!dsn\) return;/);
  assert.doesNotMatch(client + server, /replayIntegration|Replay/, 'Session Replay records notes on screen');
});
