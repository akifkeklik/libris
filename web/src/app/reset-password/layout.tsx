import { titleFor } from '@/lib/pageTitle';

export const generateMetadata = () => titleFor('reset_password_title');

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
