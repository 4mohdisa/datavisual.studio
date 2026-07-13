import SharedView from '../../components/SharedView';
import DemoTracker from '../../components/DemoTracker';

// Public zero-friction demo (1b): renders a prebuilt sample dashboard through
// the exact same read-only SharedView as a share link — no auth, no key. The
// fetch is server-side (like the share page), so no Clerk session is needed.
const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';

async function getDemo() {
  const headers = {};
  if (process.env.PROXY_SHARED_SECRET) headers['x-proxy-secret'] = process.env.PROXY_SHARED_SECRET;
  try {
    const r = await fetch(`${BACKEND}/api/demo`, { headers, cache: 'no-store' });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

export const metadata = {
  title: 'Live demo',
  description: 'A real, interactive datavisual.studio dashboard from sample data — no sign-up, no AI key required.',
  alternates: { canonical: '/demo' },
};

export default async function DemoPage() {
  const data = await getDemo();
  return (
    <>
      <DemoTracker />
      <SharedView data={data} />
    </>
  );
}
