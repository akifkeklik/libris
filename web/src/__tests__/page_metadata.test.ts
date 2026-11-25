import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const app = (...p: string[]) => join(__dirname, '..', 'app', ...p);

test('every page has its own title and unknown addresses get a translated page', () => {
  for (const r of ['ai-discovery', 'catalog', 'favorites', 'forgot-password', 'import', 'learning', 'login', 'privacy', 'reset-password', 'settings', 'signup', 'terms']) {
    assert.match(readFileSync(app(r, 'layout.tsx'), 'utf8'), /generateMetadata/, r);
  }
  assert.match(readFileSync(app('book', '[isbn]', 'page.tsx'), 'utf8'), /title: book\.title/);
  assert.match(readFileSync(app('not-found.tsx'), 'utf8'), /not_found_title/);
  assert.match(readFileSync(app('layout.tsx'), 'utf8'), /template: "%s \| Libris"/);
  assert.ok(existsSync(join(__dirname, '..', '..', 'public', 'og.png')));
});

test('signed out, the protected library link is not prefetched into a login redirect', () => {
  assert.match(readFileSync(join(__dirname, '..', 'components', 'Navbar.tsx'), 'utf8'), /href="\/favorites" prefetch=\{user \? undefined : false\}/);
});

test('auth events refresh the page only when the reader changed (a 404 page used to reload forever)', () => {
  const src = readFileSync(join(__dirname, '..', 'components', 'AuthProvider.tsx'), 'utf8');
  assert.equal(src.match(/router\.refresh\(\)/g)?.length, 1);
  assert.match(src, /if \(changed \|\| event === 'USER_UPDATED'\) \{\s*lastUserId = id;\s*router\.refresh\(\);/);
});
