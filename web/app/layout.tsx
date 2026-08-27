import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';

export const metadata: Metadata = {
  metadataBase: new URL('https://gaonone.in'),
  title: 'GaonOne — Local commerce for every village',
  description: 'Discover local shops, essentials, food and delivery in your village.',
  applicationName: 'GaonOne',
  alternates: { canonical: '/' },
  icons: {
    icon: '/icon.svg',
    shortcut: '/icon.svg',
    apple: '/icon.svg',
  },
  openGraph: {
    type: 'website',
    url: 'https://gaonone.in',
    siteName: 'GaonOne',
    title: 'GaonOne — Local commerce for every village',
    description: 'Discover local shops, essentials, food and delivery in your village.',
  },
  twitter: {
    card: 'summary',
    title: 'GaonOne — Local commerce for every village',
    description: 'Discover local shops, essentials, food and delivery in your village.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
