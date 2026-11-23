import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const read = (...p: string[]) => readFileSync(join(__dirname, '..', ...p), 'utf8');

test('every review card offers edit, new AI question and report; a reported card leaves the queue', () => {
  const card = read('components', 'ActiveRecallCard.tsx');
  assert.match(card, /<CardControls itemId=\{item\.id\}/);
  assert.match(card, /\{content\.question\}/, 'edits and regenerations show immediately');
  const controls = read('components', 'CardControls.tsx');
  for (const action of ['regenerateLearningItemAction', 'reportLearningItemAction', 'updateLearningItemAction']) assert.match(controls, new RegExp(action));
  assert.match(controls, /role="menu"/);
  assert.match(controls, /value: 'unclear'[\s\S]*value: 'wrong'[\s\S]*value: 'too_easy'[\s\S]*value: 'duplicate'[\s\S]*value: 'other'/);
  assert.match(read('components', 'LearningDashboard.tsx'), /onRemoved=\{\(\) => setQueue\(\(prev\) => prev\.filter/);
});

test('review settings: retention only when FSRS is on, bounded 80-95%, Anki export downloads an .apkg', () => {
  const s = read('components', 'ReviewSettings.tsx');
  assert.match(s, /\{fsrs && \(/);
  assert.match(s, /min=\{80\} max=\{95\}/);
  assert.match(s, /download: 'libris-cards\.apkg'/);
  assert.match(read('app', 'actions', 'learning.ts'), /desiredRetention >= 0\.8 && desiredRetention <= 0\.95/);
  assert.match(read('app', 'settings', 'page.tsx'), /\{user && <ReviewSettings \/>\}/);
});
