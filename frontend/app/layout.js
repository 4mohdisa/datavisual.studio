import './globals.css';
import { ClerkProvider } from '@clerk/nextjs';
import ErrorBoundary from '../components/ErrorBoundary';
import Identify from '../components/Identify';

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://datavisual.studio';
const DESCRIPTION =
  'Turn any dataset into a live, editable dashboard — then let a council of AI models research your question on the live web and tell you what changed. Free: bring your own AI keys.';

export const metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'datavisual.studio — living dashboards & AI-researched reports',
    template: '%s · datavisual.studio',
  },
  description: DESCRIPTION,
  applicationName: 'datavisual.studio',
  keywords: [
    'data visualization', 'live dashboard', 'BI tool', 'Power BI alternative',
    'AI research', 'multi-model AI', 'LLM council', 'dashboard from CSV',
    'connect database dashboard', 'deep research report', 'data analysis tool',
  ],
  authors: [{ name: 'Mohammed Isa', url: 'https://github.com/4mohdisa' }],
  creator: 'Mohammed Isa',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    siteName: 'datavisual.studio',
    url: SITE_URL,
    title: 'datavisual.studio — living dashboards & AI-researched reports',
    description: DESCRIPTION,
  },
  twitter: {
    card: 'summary_large_image',
    title: 'datavisual.studio — living dashboards & AI-researched reports',
    description: DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large' },
  },
};

export const viewport = {
  themeColor: '#0f0f0f',
  colorScheme: 'dark',
};

// Clerk appearance tuned to the product's oklch dark palette.
const clerkAppearance = {
  variables: {
    colorPrimary: '#4a90e2',
    colorBackground: '#1c1c1c',
    colorInputBackground: '#242424',
    colorText: '#eaeaea',
    colorTextSecondary: '#a3a3a3',
    colorInputText: '#eaeaea',
    borderRadius: '8px',
  },
  elements: {
    card: { backgroundColor: '#1c1c1c', border: '1px solid #333' },
    footer: { background: '#1c1c1c' },
  },
};

export default function RootLayout({ children }) {
  const authEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const inner = (
    <html lang="en">
      <body>
        <ErrorBoundary>{children}</ErrorBoundary>
        {/* anon→user analytics stitch — needs a ClerkProvider ancestor. */}
        {authEnabled && <Identify />}
      </body>
    </html>
  );
  // OPEN mode without Clerk keys — the whole tree renders without a provider.
  return authEnabled ? <ClerkProvider appearance={clerkAppearance}>{inner}</ClerkProvider> : inner;
}
