import { titleFor } from '@/lib/pageTitle';

export const generateMetadata = () => titleFor('nav_for_you');

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
