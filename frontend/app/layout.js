import './globals.css';
import { ClerkProvider } from '@clerk/nextjs';
import ErrorBoundary from '../components/ErrorBoundary';

export const metadata = {
  title: 'datavisual.studio',
  description:
    'Multi-model AI research and prediction platform — upload a dataset, ask anything, get a structured analytical report.',
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
      </body>
    </html>
  );
  // OPEN mode without Clerk keys — the whole tree renders without a provider.
  return authEnabled ? <ClerkProvider appearance={clerkAppearance}>{inner}</ClerkProvider> : inner;
}
