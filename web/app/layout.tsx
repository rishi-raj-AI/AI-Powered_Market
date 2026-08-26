import './globals.css';
import { Providers } from './providers';
export const metadata={title:'GaonOne — Local commerce for every village',description:'Discover local shops, essentials, food and delivery in your village.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><Providers>{children}</Providers></body></html>}
