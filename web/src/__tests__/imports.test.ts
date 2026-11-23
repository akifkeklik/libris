import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { detectSource, splitImport } from '../lib/importChunks';

const read = (...p: string[]) => readFileSync(join(__dirname, '..', ...p), 'utf8');

test('kindle files are split only after a separator, every entry survives', () => {
  const entry = (i: number) => `Book ${i} (Author)\n- Your Highlight on page ${i}\n\n${'word '.repeat(40)}${i}\n==========\n`;
  const text = Array.from({ length: 50 }, (_, i) => entry(i)).join('');
  const pieces = splitImport('kindle', text, 2000);
  assert.ok(pieces.length > 1);
  assert.ok(pieces.every((p) => p.length <= 2000 + entry(99).length));
  assert.equal(pieces.join(''), text, 'nothing lost or reordered');
  assert.ok(pieces.every((p) => p.trimEnd().endsWith('==========')), 'cuts only after a separator');
});

test('csv files are split between records, never inside a quoted multi-line field, header repeated', () => {
  const header = 'Highlight,Book Title,Book Author\n';
  const rows = Array.from({ length: 60 }, (_, i) => `"line one ${i}\nline ""two"" ${i}",Book ${i},Author\n`);
  const pieces = splitImport('readwise', header + rows.join(''), 600);
  assert.ok(pieces.length > 1);
  for (const p of pieces) {
    assert.ok(p.startsWith(header));
    assert.equal((p.match(/"/g) ?? []).length % 2, 0, 'quotes balanced in every piece');
  }
  assert.equal(pieces.map((p) => p.slice(header.length)).join(''), rows.join(''));
});

test('small files travel in one piece; BOM and CRLF are normalised', () => {
  assert.deepEqual(splitImport('kindle', '﻿a\r\nb'), ['a\nb']);
});

test('the source is detected from the file', () => {
  assert.equal(detectSource('goodreads_library_export.csv', 'Book Id,Title,Author,Exclusive Shelf'), 'goodreads');
  assert.equal(detectSource('export.csv', 'Highlight,Book Title,Book Author'), 'readwise');
  assert.equal(detectSource('My Clippings.txt', 'X (Y)\n- Your Highlight'), 'kindle');
  assert.equal(detectSource('notes.txt', 'hello'), null);
});

test('import page: approval queue, book picker for unmatched books, share target pickup, library entry point', () => {
  const page = read('app', 'import', 'page.tsx');
  assert.match(page, /decideImportsAction/);
  assert.match(page, /<BookPicker/);
  assert.match(page, /caches\.open\(SHARE_CACHE\)/);
  assert.match(page, /cache\.delete\('\/__share\/file'\)/, 'shared payload is read once');
  assert.match(read('app', 'favorites', 'page.tsx'), /href="\/import"/);
  const manifest = JSON.parse(readFileSync(join(__dirname, '..', '..', 'public', 'manifest.json'), 'utf8'));
  assert.equal(manifest.share_target.action, '/import/share');
  const sw = readFileSync(join(__dirname, '..', '..', 'public', 'sw.js'), 'utf8');
  assert.match(sw, /url\.pathname !== '\/import\/share'/);
  assert.match(sw, /file\.size <= 4 \* 1024 \* 1024/);
});
