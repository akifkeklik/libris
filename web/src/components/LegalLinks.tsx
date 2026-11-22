'use client';

import Link from 'next/link';
import { LEGAL } from '@/lib/legal';
import { usePreferences } from '@/components/PreferencesProvider';

/** Links to the privacy policy and terms, titled in the reader's language. */
export function LegalLinks({ intro }: { intro?: string }) {
  const { preferences } = usePreferences();
  const language = preferences.language;
  return (
    <p data-testid="legal-links" className="text-muted" style={{ fontSize: '0.8rem', lineHeight: 1.6, textAlign: 'center', marginTop: '1.25rem' }}>
      {intro ? `${intro} ` : ''}
      <Link href="/privacy" style={{ color: 'var(--primary)', textDecoration: 'underline' }}>{LEGAL.privacy[language].title}</Link>
      {' · '}
      <Link href="/terms" style={{ color: 'var(--primary)', textDecoration: 'underline' }}>{LEGAL.terms[language].title}</Link>
    </p>
  );
}
