import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { LEGAL } from '../lib/legal';
import { LANGUAGES } from '../lib/preferences';

test('privacy and terms exist in every language with the same structure, marked as a draft', () => {
  for (const kind of ['privacy', 'terms'] as const) {
    const en = LEGAL[kind].en;
    for (const lang of LANGUAGES) {
      const doc = LEGAL[kind][lang];
      assert.ok(doc, `${kind}.${lang} missing`);
      assert.equal(doc.sections.length, en.sections.length, `${kind}.${lang} section count`);
      assert.ok(doc.draft.trim() && doc.sections.every((s) => s.title.trim() && s.body.every((p) => p.trim())));
      if (lang !== 'en') assert.notEqual(doc.title, en.title, `${kind}.${lang} untranslated`);
    }
  }
});

test('the privacy policy states what is sent to Gemini, in every language', () => {
  for (const lang of LANGUAGES) {
    const text = JSON.stringify(LEGAL.privacy[lang]);
    assert.match(text, /Gemini/, lang);
    assert.match(text, /1[.,\s ]?500/, `${lang}: note length sent to Gemini`);
  }
});

test('legal pages are reachable from signup and settings', () => {
  const read = (...p: string[]) => readFileSync(join(__dirname, '..', 'app', ...p), 'utf8');
  assert.match(read('signup', 'page.tsx'), /<LegalLinks/);
  assert.match(read('settings', 'page.tsx'), /<LegalLinks/);
  assert.match(read('privacy', 'page.tsx'), /kind="privacy"/);
  assert.match(read('terms', 'page.tsx'), /kind="terms"/);
});
