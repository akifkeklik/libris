import { titleFor } from '@/lib/pageTitle';

export const generateMetadata = () => titleFor('nav_login');

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
