import { cache } from 'react';
import SharedView from '../../../components/SharedView';

// Server-side fetch straight to the engine (no browser round-trip). Cached per
// request so generateMetadata and the page share one fetch.
const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';

const getShare = cache(async (shareId) => {
  const headers = {};
  if (process.env.PROXY_SHARED_SECRET) headers['x-proxy-secret'] = process.env.PROXY_SHARED_SECRET;
  try {
    // encodeURIComponent is load-bearing: Next decodes %2f in the [shareId]
    // segment into real slashes, so an un-encoded id like "../../api/conversations"
    // would make fetch() retarget a different (identity-less) backend endpoint.
    // Encoding keeps it a single path segment; the backend's is_valid_id then 404s it.
    const r = await fetch(`${BACKEND}/api/public/${encodeURIComponent(shareId)}`, { headers, cache: 'no-store' });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
});

export async function generateMetadata({ params }) {
  const { shareId } = await params;
  const data = await getShare(shareId);
  // Shared links are private-by-link — never index them.
  if (!data) {
    return { title: 'Shared view', robots: { index: false, follow: false } };
  }
  const count = data.dashboard?.widgets?.length || 0;
  const description = `A live, read-only dashboard shared from datavisual.studio${count ? ` — ${count} widgets` : ''}.`;
  return {
    title: data.title,
    description,
    robots: { index: false, follow: false },
    openGraph: { title: `${data.title} · datavisual.studio`, description, type: 'website' },
    twitter: { card: 'summary_large_image', title: `${data.title} · datavisual.studio`, description },
  };
}

export default async function SharePage({ params }) {
  const { shareId } = await params;
  const data = await getShare(shareId);
  return <SharedView data={data} />;
}
