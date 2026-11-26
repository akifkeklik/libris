import test from 'node:test';
import assert from 'node:assert/strict';
import { contentSecurityPolicy } from '../../next.config';

test('the content security policy limits scripts, frames and plugins and allows the services the app uses', () => {
  const csp = contentSecurityPolicy();
  for (const rule of ["default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'", 'https://books.google.com', 'https://covers.openlibrary.org', 'https://fonts.gstatic.com']) {
    assert.ok(csp.includes(rule), rule);
  }
  assert.doesNotMatch(csp.split('; ').find((d) => d.startsWith('script-src'))!, /https?:/, 'no third-party script hosts');
});
