const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://datavisual.studio';

// Index the marketing + legal surfaces; keep the app, admin, per-user data and
// private-by-link share views out of search results.
export default function robots() {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/studio', '/chat', '/dashboard', '/admin', '/share', '/api'],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
