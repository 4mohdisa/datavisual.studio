// Dedicated first-party analytics sink (1c). Separate from the [...path] proxy
// on purpose — anonymous visitors must be able to post funnel events, and the
// plan is explicit that adding auth-exempt prefixes to that proxy is the exact
// pattern that produced past criticals. This route forwards to the backend with
// the proxy secret and, when signed in, the trusted identity header.
import { auth } from '@clerk/nextjs/server';

export const dynamic = 'force-dynamic';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';
const AUTH_ENABLED = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export async function POST(req) {
  let body;
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false }, { status: 400 });
  }

  const headers = { 'content-type': 'application/json' };
  if (process.env.PROXY_SHARED_SECRET) headers['x-proxy-secret'] = process.env.PROXY_SHARED_SECRET;
  if (AUTH_ENABLED) {
    try {
      const { userId } = await auth();
      if (userId) headers['x-clerk-user-id'] = userId; // stitch server-side too
    } catch { /* anonymous is fine — user_id stays null */ }
  }

  try {
    const r = await fetch(`${BACKEND}/api/events`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
    return Response.json({ ok: r.ok });
  } catch {
    return Response.json({ ok: false }, { status: 502 });
  }
}
