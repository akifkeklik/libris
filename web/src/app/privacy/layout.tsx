import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { LEGAL } from '@/lib/legal';
import { resolveLanguage } from '@/lib/preferences';

export async function generateMetadata(): Promise<Metadata> {
  return { title: LEGAL.privacy[resolveLanguage((await cookies()).get('libris_lang')?.value)].title };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
