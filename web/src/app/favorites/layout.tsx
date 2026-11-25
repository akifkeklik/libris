import { titleFor } from '@/lib/pageTitle';

export const generateMetadata = () => titleFor('nav_my_library');

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
