import { titleFor } from '@/lib/pageTitle';

export const generateMetadata = () => titleFor('import_title');

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
