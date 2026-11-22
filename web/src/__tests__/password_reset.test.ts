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

test('Google sign-in is opt-in and returns through the callback', () => {
  const src = readFileSync(join(__dirname, '..', 'components', 'OAuthButtons.tsx'), 'utf8');
  assert.match(src, /NEXT_PUBLIC_AUTH_GOOGLE_ENABLED === 'true'/, 'must stay hidden until the provider is configured');
  assert.match(src, /if \(!GOOGLE_AUTH_ENABLED\) return null;/);
  assert.match(src, /\/auth\/callback\?next=\$\{encodeURIComponent\(redirect\)\}/);
  for (const page of [['login', 'page.tsx'], ['signup', 'page.tsx']]) assert.match(read(...page), /<OAuthButtons redirect=/);
});

test('signup no longer hardcodes English button and link text', () => {
  assert.doesNotMatch(read('signup', 'page.tsx'), /'Creating account\.\.\.'|'Sign up'|Go to Log in/);
});
