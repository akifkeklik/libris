'use client';

import { useEffect, useId, useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { searchCatalogAction } from '@/app/actions/catalog';
import { usePreferences } from '@/components/PreferencesProvider';
import type { Book } from '@/types';

/** Search the catalogue and pick one book (used where an import entry has no matched book). */
export function BookPicker({ initialQuery, onPick, label }: { initialQuery: string; onPick: (book: Book) => void; label: string }) {
  const { t } = usePreferences();
  const id = useId();
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<Book[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      searchCatalogAction(q, 6).then((res) => {
        if (cancelled) return;
        setResults(res.success ? res.books : []);
        setLoading(false);
      });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  return (
    <div className="book-picker">
      <label htmlFor={id} className="input-label" style={{ fontSize: '0.8rem' }}>{label}</label>
      <div style={{ position: 'relative' }}>
        <Search size={14} aria-hidden="true" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted-strong)' }} />
        <input id={id} className="input-field" value={query} onChange={(e) => setQuery(e.target.value)}
          style={{ width: '100%', paddingLeft: '2.2rem', height: '38px', fontSize: '0.85rem' }} autoComplete="off" />
        {loading && <Loader2 size={14} className="animate-spin" aria-hidden="true" style={{ position: 'absolute', right: '0.75rem', top: '50%', marginTop: -7 }} />}
      </div>
      {results && (
        <ul className="book-picker__results" aria-live="polite">
          {results.length === 0 && <li className="text-muted" style={{ padding: '0.5rem 0.25rem', fontSize: '0.8rem' }}>{t('import_no_book_found')}</li>}
          {results.map((b) => (
            <li key={b.isbn13}>
              <button type="button" onClick={() => onPick(b)} className="book-picker__option">
                <span style={{ fontWeight: 600 }}>{b.title}</span>
                <span className="text-muted" style={{ fontSize: '0.78rem' }}>{b.authors}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
