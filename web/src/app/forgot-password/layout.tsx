import { titleFor } from '@/lib/pageTitle';

export const generateMetadata = () => titleFor('forgot_password_title');

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
