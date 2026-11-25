import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { translate, type TranslationKey } from '@/lib/i18n';
import { resolveLanguage } from '@/lib/preferences';

/** A page's <title> in the reader's language; the root layout adds " | Libris". */
export async function titleFor(key: TranslationKey): Promise<Metadata> {
  const lang = resolveLanguage((await cookies()).get('libris_lang')?.value);
  return { title: translate(lang, key) };
}
