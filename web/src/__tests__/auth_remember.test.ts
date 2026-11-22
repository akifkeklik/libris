import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { applyRemember, isSessionOnly } from '../lib/supabase/remember';
import { isExistingAccount } from '../lib/authErrors';

const read = (...p: string[]) => readFileSync(join(__dirname, '..', ...p), 'utf8');

test('unticked "remember me" turns auth cookies into browser-session cookies, deletions untouched', () => {
  const opts = { path: '/', sameSite: 'lax', maxAge: 34560000 };
  assert.deepEqual(applyRemember(opts, true), { path: '/', sameSite: 'lax' });
  assert.deepEqual(applyRemember(opts, false), opts);
  assert.deepEqual(applyRemember({ path: '/', maxAge: 0 }, true), { path: '/', maxAge: 0 }, 'sign-out must still delete');
  assert.equal(isSessionOnly('0'), true);
  assert.equal(isSessionOnly(undefined), false);
});

test('every Supabase client honours the remember choice and every sign-in form offers it', () => {
  for (const f of ['client.ts', 'server.ts', 'middleware.ts']) {
    assert.match(read('lib', 'supabase', f), /applyRemember\(options, sessionOnly\)/, f);
  }
  for (const page of [['app', 'login', 'page.tsx'], ['app', 'signup', 'page.tsx']]) {
    const src = read(...page);
    assert.match(src, /<RememberMe checked=\{remember\}/, page.join('/'));
    assert.match(src, /setRememberChoice\(remember\)/, page.join('/'));
    assert.match(src, /remember=\{remember\}/, 'Google sign-in gets the same choice');
  }
  assert.match(read('components', 'OAuthButtons.tsx'), /setRememberChoice\(remember\)/);
});

test('an already registered address is recognised in both Supabase shapes', () => {
  assert.equal(isExistingAccount(null, []), true);
  assert.equal(isExistingAccount({ code: 'user_already_exists' }), true);
  assert.equal(isExistingAccount({ message: 'User already registered' }), true);
  assert.equal(isExistingAccount({ code: 'weak_password' }), false);
  assert.equal(isExistingAccount(null, [{}]), false);
});

test('sign-up hands the address to log-in through sessionStorage, not the URL', () => {
  const signup = read('app', 'signup', 'page.tsx');
  assert.match(signup, /sessionStorage\.setItem\(LOGIN_EMAIL_HANDOFF/);
  assert.match(signup, /signup_exists_body/);
  assert.doesNotMatch(signup, /[?&]email=/);
  const login = read('app', 'login', 'page.tsx');
  assert.match(login, /sessionStorage\.removeItem\(LOGIN_EMAIL_HANDOFF\)/, 'read once');
  assert.match(login, /passwordRef\.current\?\.focus\(\)/);
});
