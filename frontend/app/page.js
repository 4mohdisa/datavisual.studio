import Landing from '../components/landing/Landing';

export const metadata = {
  // Homepage owns the full brand title (no template suffix).
  title: { absolute: 'datavisual.studio — living dashboards & AI-researched reports' },
  description:
    'Upload a file or connect your database. Get an instantly editable dashboard, then let a council of AI models research your question on the live web — and tell you what changed.',
  alternates: { canonical: '/' },
};

// Structured data — helps search engines understand what the app is.
const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'datavisual.studio',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  description:
    'Turn any dataset into a live, editable dashboard, then let a council of AI models research your question on the live web and tell you what changed.',
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  featureList: [
    'Instant dashboards from CSV, Excel, JSON or a SQL/REST connection',
    'Edit dashboards by chat or by hand',
    'Multi-model AI research council with cited reports',
    'Living monitor — one update shows what changed',
    'Public read-only share links',
    'PDF and HTML export',
  ],
  author: {
    '@type': 'Person',
    name: 'Mohammed Isa',
    url: 'https://isaxcode.com',
    sameAs: ['https://github.com/4mohdisa'],
  },
};

export default function LandingPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Landing />
    </>
  );
}
