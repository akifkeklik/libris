import Link from 'next/link';
import { cookies } from 'next/headers';
import { translate } from '@/lib/i18n';
import { resolveLanguage } from '@/lib/preferences';

/** Landing page of the one-click unsubscribe link in reminder e-mails. */
export default async function ReminderUnsubscribedPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const lang = resolveLanguage((await cookies()).get('libris_lang')?.value);
  const ok = (await searchParams).status === 'ok';
  return (
    <div className="container" style={{ maxWidth: '560px', padding: '4rem 1.25rem', textAlign: 'center' }}>
      <h1 style={{ fontSize: '1.6rem', marginBottom: '0.75rem' }}>
        {translate(lang, ok ? 'unsubscribed_title' : 'unsubscribed_invalid_title')}
      </h1>
      <p style={{ lineHeight: 1.6 }} data-testid="unsubscribed-message">
        {translate(lang, ok ? 'unsubscribed_body' : 'unsubscribed_invalid_body')}
      </p>
      <p style={{ marginTop: '1.5rem' }}>
        <Link href="/settings#reminders" className="btn btn-outline">{translate(lang, 'reminders_open_settings')}</Link>
      </p>
    </div>
  );
}
