'use client';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { CheckCircle2, FileUp, Loader2, Lock, Upload } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';
import { usePreferences } from '@/components/PreferencesProvider';
import { BookPicker } from '@/components/BookPicker';
import { Select } from '@/components/Select';
import { decideImportsAction, getImportQueueAction, importPieceAction } from '@/app/actions/imports';
import { createNote } from '@/app/actions/notes';
import { MAX_FILE_BYTES, detectSource, splitImport, type ImportSource } from '@/lib/importChunks';
import type { ImportItem, ImportSummary } from '@/lib/api';
import type { TranslationKey } from '@/lib/i18n';

const SOURCES: { id: ImportSource; title: TranslationKey; hint: TranslationKey; accept: string }[] = [
  { id: 'kindle', title: 'import_source_kindle', hint: 'import_source_kindle_hint', accept: '.txt,text/plain' },
  { id: 'readwise', title: 'import_source_readwise', hint: 'import_source_readwise_hint', accept: '.csv,text/csv' },
  { id: 'goodreads', title: 'import_source_goodreads', hint: 'import_source_goodreads_hint', accept: '.csv,text/csv' },
];
const SHARE_CACHE = 'libris-share-target';
const BATCH = 100;

type Group = { key: string; title: string; author: string | null; bookId: string | null; items: ImportItem[] };

function groupItems(items: ImportItem[]): Group[] {
  const map = new Map<string, Group>();
  for (const it of items) {
    const key = `${it.book_title}\u0000${it.book_author ?? ''}`;
    if (!map.has(key)) map.set(key, { key, title: it.book_title, author: it.book_author, bookId: it.book_id, items: [] });
    const g = map.get(key)!;
    g.items.push(it);
    if (!g.bookId && it.book_id) g.bookId = it.book_id;
  }
  return [...map.values()];
}

function ImportFlow() {
  const { t } = usePreferences();
  const params = useSearchParams();
  const [source, setSource] = useState<ImportSource>('kindle');
  const [busy, setBusy] = useState<string | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<ImportItem[] | null>(null);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [overrides, setOverrides] = useState<Record<string, { id: string; title: string }>>({});
  const [highlightAs, setHighlightAs] = useState<'key_takeaway' | 'personal_note'>('key_takeaway');
  const [result, setResult] = useState<string | null>(null);
  const [sharedText, setSharedText] = useState<string | null>(null);
  const [sharedBook, setSharedBook] = useState<{ id: string; title: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const applyQueue = useCallback((q: { items: ImportItem[]; pending: number } | null) => {
    setQueue(q?.items ?? []);
    setPendingTotal(q?.pending ?? 0);
    setSelected(new Set((q?.items ?? []).map((i) => i.id)));
  }, []);
  const loadQueue = useCallback(async () => applyQueue(await getImportQueueAction()), [applyQueue]);

  const runImport = useCallback(async (file: File, chosen?: ImportSource) => {
    setError(null);
    setSummary(null);
    setResult(null);
    if (file.size > MAX_FILE_BYTES) {
      setError(t('import_file_too_large'));
      return;
    }
    const text = await file.text();
    const detected = detectSource(file.name, text.slice(0, 4000));
    const src = detected ?? chosen ?? source;
    if (detected) setSource(detected);
    const pieces = splitImport(src, text);
    const total: ImportSummary = { parsed: 0, new: 0, duplicates: 0, skipped: 0, truncated: 0, books: 0, books_matched: 0 };
    for (let i = 0; i < pieces.length; i++) {
      setBusy(pieces.length > 1 ? t('import_progress', { current: i + 1, total: pieces.length }) : t('import_reading'));
      const res = await importPieceAction(src, pieces[i]);
      if (!res.ok) {
        setBusy(null);
        setError(res.reason === 'invalid' ? t('import_file_invalid', { source: t(SOURCES.find((s) => s.id === src)!.title) })
          : res.reason === 'too_large' ? t('import_file_too_large') : t('import_unavailable'));
        if (i > 0) await loadQueue();
        return;
      }
      for (const k of Object.keys(total) as (keyof ImportSummary)[]) total[k] += res.summary[k] ?? 0;
    }
    setBusy(null);
    setSummary(total);
    await loadQueue();
  }, [loadQueue, source, t]);

  useEffect(() => {
    // Queue first; then anything shared to Libris from another app (PWA share target).
    const shared = params.get('shared') === '1';
    getImportQueueAction().then(async (q) => {
      applyQueue(q);
      if (!shared || typeof caches === 'undefined') return;
      try {
        const cache = await caches.open(SHARE_CACHE);
        const fileRes = await cache.match('/__share/file');
        const textRes = await cache.match('/__share/text');
        await cache.delete('/__share/file');
        await cache.delete('/__share/text');
        if (fileRes) {
          const name = decodeURIComponent(fileRes.headers.get('x-file-name') || 'shared.txt');
          await runImport(new File([await fileRes.blob()], name));
        } else if (textRes) {
          const txt = (await textRes.text()).trim();
          if (txt) setSharedText(txt.slice(0, 5000));
        }
      } catch {
        // Cache Storage unavailable: nothing was shared to pick up.
      }
    });
  }, [params, applyQueue, runImport]);

  const groups = useMemo(() => groupItems(queue ?? []), [queue]);

  const toggle = (ids: string[], on: boolean) => setSelected((prev) => {
    const next = new Set(prev);
    ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
    return next;
  });

  const decide = async (action: 'approve' | 'reject', ids: string[]) => {
    if (!ids.length) return;
    setResult(null);
    setSummary(null);
    setError(null);
    let approved = 0, rejected = 0, created = 0, deferred = 0, needBook = 0, failed = 0;
    for (let i = 0; i < ids.length; i += BATCH) {
      const chunk = ids.slice(i, i + BATCH);
      setBusy(t(action === 'approve' ? 'import_approving' : 'import_dismissing'));
      const book_overrides: Record<string, string> = {};
      if (action === 'approve') {
        for (const g of groups) {
          const o = overrides[g.key];
          if (o) g.items.forEach((it) => { if (chunk.includes(it.id)) book_overrides[it.id] = o.id; });
        }
      }
      const res = await decideImportsAction(action === 'approve'
        ? { action, ids: chunk, highlight_as: highlightAs, book_overrides }
        : { action, ids: chunk });
      if (!res.ok) {
        setError(t('import_unavailable'));
        break;
      }
      approved += res.result.approved ?? 0;
      rejected += res.result.rejected ?? 0;
      created += res.result.questions_created ?? 0;
      deferred += res.result.questions_deferred ?? 0;
      needBook += res.result.needs_book?.length ?? 0;
      failed += res.result.failed ?? 0;
    }
    setBusy(null);
    if (action === 'approve') {
      const parts = [t('import_approved', { count: approved })];
      if (deferred) parts.push(t('import_questions_status', { now: created, later: deferred }));
      else if (created) parts.push(t('import_questions_ready', { count: created }));
      if (needBook) parts.push(t('import_needs_book', { count: needBook }));
      if (failed) parts.push(t('import_some_failed', { count: failed }));
      setResult(parts.join(' '));
    } else {
      setResult(t('import_dismissed', { count: rejected }));
    }
    await loadQueue();
  };

  const saveShared = async () => {
    if (!sharedText || !sharedBook) return;
    setBusy(t('import_approving'));
    const res = await createNote(sharedBook.id, 'key_takeaway', sharedText);
    setBusy(null);
    if (res.success) {
      setSharedText(null);
      setResult(t('import_shared_saved', { title: sharedBook.title }));
    } else {
      setError(t('import_unavailable'));
    }
  };

  const current = SOURCES.find((s) => s.id === source)!;
  const shelfLabel = (s: ImportItem['shelf']) => (s === 'finished' ? t('status_finished') : s === 'reading' ? t('status_reading') : t('status_want_to_read'));

  return (
    <div className="container" style={{ maxWidth: 920, padding: '2rem 1rem 4rem' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.4rem' }}>{t('import_title')}</h1>
      <p className="text-muted" style={{ marginBottom: '1.75rem', lineHeight: 1.6 }}>{t('import_subtitle')}</p>

      {sharedText && (
        <section className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }} data-testid="import-shared-text">
          <h2 style={{ fontSize: '1.15rem', marginBottom: '0.75rem' }}>{t('import_shared_title')}</h2>
          <blockquote style={{ margin: '0 0 1rem', padding: '0.75rem 1rem', borderLeft: '3px solid var(--primary)', whiteSpace: 'pre-wrap' }}>{sharedText}</blockquote>
          {sharedBook
            ? <p style={{ marginBottom: '1rem' }}>{t('import_book_chosen', { title: sharedBook.title })}</p>
            : <BookPicker initialQuery="" label={t('import_pick_book')} onPick={(b) => setSharedBook({ id: b.isbn13, title: b.title })} />}
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <button type="button" className="btn btn-primary" disabled={!sharedBook || !!busy} onClick={saveShared}>{t('import_save_as_takeaway')}</button>
            <button type="button" className="btn btn-outline" onClick={() => setSharedText(null)}>{t('import_dismiss')}</button>
          </div>
        </section>
      )}

      <section className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="input-label" style={{ marginBottom: '0.75rem' }}>{t('import_choose_source')}</legend>
          <div className="import-sources">
            {SOURCES.map((s) => (
              <label key={s.id} className={`import-source${source === s.id ? ' is-active' : ''}`}>
                <input type="radio" name="import-source" value={s.id} checked={source === s.id} onChange={() => setSource(s.id)} />
                <span className="import-source__title">{t(s.title)}</span>
                <span className="import-source__hint">{t(s.hint)}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <input ref={fileRef} type="file" accept={current.accept} hidden data-testid="import-file"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void runImport(f, source); e.target.value = ''; }} />
        <button type="button" className="btn btn-primary" style={{ marginTop: '1.25rem', display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }}
          onClick={() => fileRef.current?.click()} disabled={!!busy}>
          <FileUp size={16} aria-hidden="true" /> {t('import_choose_file')}
        </button>
        <p className="text-muted" style={{ fontSize: '0.8rem', marginTop: '0.75rem' }}>{t('import_privacy_note')}</p>
      </section>

      <div role="status" aria-live="polite" style={{ minHeight: '1.5rem', marginBottom: '1rem' }}>
        {busy && <span style={{ display: 'inline-flex', gap: '0.5rem', alignItems: 'center' }}><Loader2 size={16} className="animate-spin" aria-hidden="true" /> {busy}</span>}
        {!busy && summary && (
          <span data-testid="import-summary">{t('import_summary', { new: summary.new, duplicates: summary.duplicates, books: summary.books, matched: summary.books_matched })}
            {summary.skipped > 0 && ` ${t('import_skipped', { count: summary.skipped })}`}
            {summary.truncated > 0 && ` ${t('import_truncated', { count: summary.truncated })}`}</span>
        )}
        {!busy && result && <span data-testid="import-result" style={{ display: 'block' }}><CheckCircle2 size={15} aria-hidden="true" style={{ verticalAlign: '-2px', color: 'var(--success, var(--primary))' }} /> {result}</span>}
        {error && <span role="alert" style={{ color: 'var(--danger)', display: 'block' }}>{error}</span>}
      </div>

      {queue === null ? (
        <div className="glass-panel animate-pulse" style={{ height: 160 }} />
      ) : queue.length === 0 ? (
        <section className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }} data-testid="import-queue-empty">
          <Upload size={28} aria-hidden="true" style={{ color: 'var(--primary)', marginBottom: '0.75rem' }} />
          <p style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{t('import_queue_empty_title')}</p>
          <p className="text-muted" style={{ fontSize: '0.9rem' }}>{t('import_queue_empty_body')}</p>
        </section>
      ) : (
        <section data-testid="import-queue">
          <div className="import-toolbar glass-panel">
            <div>
              <h2 style={{ fontSize: '1.2rem', margin: 0 }}>{t('import_queue_title', { count: pendingTotal })}</h2>
              {pendingTotal > queue.length && <p className="text-muted" style={{ fontSize: '0.8rem', margin: '0.25rem 0 0' }}>{t('import_queue_more', { shown: queue.length })}</p>}
            </div>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <span className="text-muted" style={{ fontSize: '0.85rem' }} id="import-as-label">{t('import_highlights_become')}</span>
              <Select<'key_takeaway' | 'personal_note'> value={highlightAs} onChange={setHighlightAs} labelledBy="import-as-label" size="sm"
                options={[{ value: 'key_takeaway', label: t('import_as_cards') }, { value: 'personal_note', label: t('import_as_notes') }]} />
              <button type="button" className="btn btn-primary" disabled={!!busy || selected.size === 0} data-testid="import-approve-selected"
                onClick={() => decide('approve', [...selected])}>{t('import_approve_selected', { count: selected.size })}</button>
              <button type="button" className="btn btn-outline" disabled={!!busy || selected.size === 0}
                onClick={() => decide('reject', [...selected])}>{t('import_dismiss_selected', { count: selected.size })}</button>
            </div>
          </div>

          {groups.map((g) => {
            const ids = g.items.map((i) => i.id);
            const allOn = ids.every((id) => selected.has(id));
            const chosen = overrides[g.key];
            return (
              <article key={g.key} className="glass-panel import-group" data-testid="import-group">
                <header className="import-group__head">
                  <label style={{ display: 'flex', gap: '0.6rem', alignItems: 'flex-start', cursor: 'pointer' }}>
                    <input type="checkbox" checked={allOn} onChange={(e) => toggle(ids, e.target.checked)} aria-label={t('import_select_book', { title: g.title })} style={{ marginTop: '0.35rem' }} />
                    <span>
                      <span style={{ fontWeight: 700, display: 'block' }}>{g.title}</span>
                      {g.author && <span className="text-muted" style={{ fontSize: '0.85rem' }}>{g.author}</span>}
                    </span>
                  </label>
                  <span className={`import-badge${g.bookId || chosen ? ' is-ok' : ''}`}>
                    {chosen ? t('import_book_chosen', { title: chosen.title }) : g.bookId ? t('import_matched') : t('import_not_matched')}
                  </span>
                </header>
                {!g.bookId && !chosen && (
                  <BookPicker initialQuery={g.title} label={t('import_pick_book')} onPick={(b) => setOverrides((o) => ({ ...o, [g.key]: { id: b.isbn13, title: b.title } }))} />
                )}
                <ul className="import-items">
                  {g.items.map((it) => (
                    <li key={it.id}>
                      <label className="import-item">
                        <input type="checkbox" checked={selected.has(it.id)} onChange={(e) => toggle([it.id], e.target.checked)} />
                        <span>
                          <span className="import-kind">{it.kind === 'shelf' ? shelfLabel(it.shelf) : t(it.kind === 'note' ? 'import_kind_note' : 'import_kind_highlight')}{it.location ? ` · ${it.location}` : ''}</span>
                          {it.content && <span className="import-item__text">{it.content}</span>}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}

export default function ImportPage() {
  const { user, loading } = useAuth();
  const { t } = usePreferences();
  if (loading) return <div className="container" style={{ padding: '3rem 1rem' }}><div className="glass-panel animate-pulse" style={{ height: 240 }} /></div>;
  if (!user) {
    return (
      <div className="container" style={{ maxWidth: 440, padding: '4rem 1rem', textAlign: 'center' }}>
        <Lock size={32} aria-hidden="true" style={{ color: 'var(--primary)', marginBottom: '1rem' }} />
        <h1 style={{ fontSize: '1.6rem', marginBottom: '0.5rem' }}>{t('import_title')}</h1>
        <p className="text-muted" style={{ marginBottom: '1.5rem' }}>{t('import_login_required')}</p>
        <Link href="/login?redirect=/import" className="btn btn-primary">{t('nav_login')}</Link>
      </div>
    );
  }
  return (
    <Suspense fallback={null}>
      <ImportFlow />
    </Suspense>
  );
}
