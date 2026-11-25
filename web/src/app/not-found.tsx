import Link from 'next/link';
import { cookies } from 'next/headers';
import { BookX, Compass, House } from 'lucide-react';
import { translate } from '@/lib/i18n';
import { resolveLanguage } from '@/lib/preferences';

export default async function NotFound() {
  const lang = resolveLanguage((await cookies()).get('libris_lang')?.value);
  return (
    <div className="container" style={{ maxWidth: 560, padding: '6rem 1.25rem', textAlign: 'center' }}>
      <BookX size={48} color="var(--primary)" aria-hidden="true" style={{ marginBottom: '1.25rem' }} />
      <h1 style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>{translate(lang, 'not_found_title')}</h1>
      <p className="text-muted" style={{ lineHeight: 1.6, marginBottom: '2rem' }}>{translate(lang, 'not_found_body')}</p>
      <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
        <Link href="/" className="btn btn-primary"><House size={16} aria-hidden="true" /> {translate(lang, 'not_found_home')}</Link>
        <Link href="/catalog" className="btn btn-outline"><Compass size={16} aria-hidden="true" /> {translate(lang, 'explore_catalog_cta')}</Link>
      </div>
    </div>
  );
}
