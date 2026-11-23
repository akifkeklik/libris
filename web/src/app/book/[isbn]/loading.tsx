import { cookies } from 'next/headers';
import { translate } from '@/lib/i18n';
import { resolveLanguage } from '@/lib/preferences';
import { BookDetailSkeleton } from '@/components/Skeleton';
import { SlowServerNotice } from '@/components/SlowServerNotice';

export default async function BookLoading() {
  const lang = resolveLanguage((await cookies()).get('libris_lang')?.value);
  return (
    <>
      <div className="container" style={{ paddingTop: '1.5rem' }}>
        <SlowServerNotice />
      </div>
      <BookDetailSkeleton label={translate(lang, 'loading_book_details')} />
    </>
  );
}
