import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { sanitizeRedirect } from '../lib/safeRedirect';

const APP = join(__dirname, '..', 'app');
const read = (...p: string[]) => readFileSync(join(APP, ...p), 'utf8');

test('forgot-password shows one message whatever happens (no account enumeration)', () => {
  const src = read('forgot-password', 'page.tsx');
  assert.match(src, /finally \{[\s\S]*setSent\(true\)/, 'confirmation must not depend on the result');
  assert.doesNotMatch(src, /user not found|no account/i);
});

test('reset e-mail and OAuth return through the callback to a same-site path only', () => {
  assert.match(read('forgot-password', 'page.tsx'), /\/auth\/callback\?next=\/reset-password/);
  const route = read('auth', 'callback', 'route.ts');
  assert.match(route, /exchangeCodeForSession/);
  assert.match(route, /sanitizeRedirect\(searchParams\.get\('next'\)\)/);
  assert.equal(sanitizeRedirect('//evil.example/x'), '/catalog');
  assert.equal(sanitizeRedirect('https://evil.example'), '/catalog');
  assert.equal(sanitizeRedirect('/reset-password'), '/reset-password');
});

test('login links to password reset and no longer hardcodes English button text', () => {
  const src = read('login', 'page.tsx');
  assert.match(src, /href="\/forgot-password"/);
  assert.doesNotMatch(src, /'Logging in\.\.\.'|'Log in'/);
});
