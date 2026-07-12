const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://datavisual.studio';

// Only the public, indexable pages. The app and share views are noindex.
export default function sitemap() {
  return [
    { url: `${SITE_URL}/`, changeFrequency: 'weekly', priority: 1 },
    { url: `${SITE_URL}/privacy`, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/terms`, changeFrequency: 'yearly', priority: 0.3 },
  ];
}
