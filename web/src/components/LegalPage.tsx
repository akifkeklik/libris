import { cookies } from 'next/headers';
import Link from 'next/link';
import { LEGAL, type LegalKind } from '@/lib/legal';
import { resolveLanguage } from '@/lib/preferences';

/** Renders a legal document in the reader's language (server component, no client JS). */
export async function LegalPage({ kind }: { kind: LegalKind }) {
  const lang = resolveLanguage((await cookies()).get('libris_lang')?.value);
  const doc = LEGAL[kind][lang];
  const other: LegalKind = kind === 'privacy' ? 'terms' : 'privacy';
  return (
    <main className="container" style={{ maxWidth: '760px', padding: '3rem 1.25rem 4rem' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{doc.title}</h1>
      <p role="note" data-testid="legal-draft" style={{ padding: '0.75rem 1rem', borderRadius: '10px', background: 'var(--tint-3)', fontSize: '0.875rem', lineHeight: 1.5 }}>
        {doc.draft}
      </p>
      <p className="text-muted" style={{ fontSize: '0.85rem' }}>{doc.updated}</p>
      {doc.sections.map((s) => (
        <section key={s.title} style={{ marginTop: '1.75rem' }}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>{s.title}</h2>
          {s.body.map((p, i) => <p key={i} style={{ lineHeight: 1.7, margin: '0 0 0.75rem' }}>{p}</p>)}
        </section>
      ))}
      <p style={{ marginTop: '2.5rem' }}>
        <Link href={`/${other}`} style={{ color: 'var(--primary)' }}>{LEGAL[other][lang].title}</Link>
      </p>
    </main>
  );
}
