import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'CareRelay — A little less to carry',
  description: 'A private, local-first family coordination workspace. Every plan starts with evidence and a human decision.',
};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
