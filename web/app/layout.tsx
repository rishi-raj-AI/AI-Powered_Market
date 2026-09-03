import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';
import { ConnectivityBanner } from '@/components/ConnectivityBanner';

export const metadata: Metadata = {
  metadataBase: new URL('https://gaonone.in'),
  title: 'GaonOne — Local commerce around you',
  description: 'Discover local shops, essentials, food and delivery across your area or neighbourhood.',
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
    title: 'GaonOne — Local commerce around you',
    description: 'Discover local shops, essentials, food and delivery across your area or neighbourhood.',
  },
  twitter: {
    card: 'summary',
    title: 'GaonOne — Local commerce around you',
    description: 'Discover local shops, essentials, food and delivery across your area or neighbourhood.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers><ConnectivityBanner/>{children}</Providers>
      </body>
    </html>
  );
}
