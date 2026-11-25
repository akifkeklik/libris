import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { LEGAL } from '../lib/legal';

test('legal pages have no unfilled placeholders, say it is a portfolio project and still say draft', () => {
  for (const kind of ['privacy', 'terms'] as const) {
    for (const [lang, doc] of Object.entries(LEGAL[kind])) {
      const text = doc.draft + doc.sections.map((s) => s.title + s.body.join(' ')).join(' ');
      assert.doesNotMatch(text, /\[[^\]]+\]/, `${kind} ${lang}`);
      assert.match(doc.draft, /Akif Keklik/);
      assert.match(doc.draft, /DRAFT|TASLAK|ENTWURF|BORRADOR|PROJET|BOZZA/);
    }
  }
});

test('the tab icon is the Libris icon with the usual sizes, not the framework default', () => {
  const ico = readFileSync(join(__dirname, '..', 'app', 'favicon.ico'));
  assert.deepEqual([ico.readUInt16LE(0), ico.readUInt16LE(2), ico.readUInt16LE(4)], [0, 1, 3]);
  assert.deepEqual([0, 1, 2].map((i) => ico.readUInt8(6 + 16 * i)), [16, 32, 48]);
});
