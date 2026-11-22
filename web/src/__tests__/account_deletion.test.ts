import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ApiService } from '../lib/api';

const read = (...p: string[]) => readFileSync(join(__dirname, '..', ...p), 'utf8');

test('deleteAccount sends DELETE /api/account with an explicit confirmation and no caching', async () => {
  const realFetch = globalThis.fetch;
  let captured: { url: string; init: RequestInit } | null = null;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    captured = { url: String(url), init };
    return new Response(JSON.stringify({ status: 'deleted' }), { status: 200 });
  }) as typeof fetch;
  try {
    assert.equal(await ApiService.deleteAccount(), 200);
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.ok(captured);
  const { url, init } = captured as { url: string; init: RequestInit };
  assert.match(url, /\/api\/account$/);
  assert.equal(init.method, 'DELETE');
  assert.equal(init.cache, 'no-store');
  assert.deepEqual(JSON.parse(String(init.body)), { confirm: true });
});

test('the delete button stays disabled until the reader types their own e-mail', () => {
  const src = read('components', 'DeleteAccountSection.tsx');
  assert.match(src, /typed\.trim\(\)\.toLowerCase\(\) === email\.trim\(\)\.toLowerCase\(\)/);
  assert.match(src, /disabled=\{!confirmed \|\| busy\}/);
  assert.match(src, /auth\.signOut\(\)/, 'the deleted account must be signed out');
  assert.match(read('app', 'settings', 'page.tsx'), /<DeleteAccountSection email=\{user\.email\}/);
});
