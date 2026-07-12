// Authenticated gateway in front of the FastAPI engine. The browser never
// talks to the engine directly: this route verifies the Clerk session, then
// forwards the request with trusted identity headers. The BACKEND owns
// everything else — it maps the Clerk id to its own internal user id and
// scopes all data per user on its local disk. Streams SSE through untouched.
import { auth, currentUser } from '@clerk/nextjs/server';

export const dynamic = 'force-dynamic';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';
const AUTH_ENABLED = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

// Owner-only endpoints — end users must never reach the model/key config.
const BLOCKED_PREFIXES = ['api/settings'];

async function handle(req, ctx) {
  const { path: parts } = await ctx.params;
  const path = (parts || []).join('/');
  const search = new URL(req.url).search;

  // Reject path traversal. Next decodes %2f inside catch-all segments into real
  // slashes, so a request like `api/public/../../api/conversations` would keep
  // its `api/public` prefix (skipping auth) yet fetch() would normalize it to a
  // different, identity-scoped endpoint — an auth bypass. Refuse any `..` segment.
  if (path.split('/').some((seg) => seg === '..' || seg === '.')) {
    return Response.json({ detail: 'Bad request' }, { status: 400 });
  }

  if (BLOCKED_PREFIXES.some((p) => path.startsWith(p))) {
    return Response.json({ detail: 'This endpoint is managed by the platform' }, { status: 403 });
  }

  // Identity headers the backend trusts (it resolves its own internal user id).
  const headers = new Headers();
  const contentType = req.headers.get('content-type');
  if (contentType) headers.set('content-type', contentType);
  if (process.env.PROXY_SHARED_SECRET) headers.set('x-proxy-secret', process.env.PROXY_SHARED_SECRET);

  // Admin is gated by ADMIN_PASSWORD on the backend, not by a Clerk session —
  // pass the password header through and skip the sign-in requirement.
  if (path.startsWith('api/admin')) {
    const adminPassword = req.headers.get('x-admin-password');
    if (adminPassword) headers.set('x-admin-password', adminPassword);
  } else if (path.startsWith('api/public/')) {
    // Public share view — the token in the URL is the capability; no session.
    // Bounded to `api/public/` so a future `api/publicX` route can't inherit it.
  } else if (AUTH_ENABLED) {
    const { userId } = await auth();
    if (!userId) return Response.json({ detail: 'Sign in to continue' }, { status: 401 });
    headers.set('x-clerk-user-id', userId);
    // Name/email are best-effort profile details for the local registry.
    try {
      const user = await currentUser();
      const email = user?.primaryEmailAddress?.emailAddress;
      const name = [user?.firstName, user?.lastName].filter(Boolean).join(' ');
      if (email) headers.set('x-user-email', email);
      if (name) headers.set('x-user-name', name);
    } catch { /* identity id alone is sufficient */ }
  }

  let body;
  if (req.method !== 'GET' && req.method !== 'HEAD') body = await req.blob();

  let upstream;
  try {
    upstream = await fetch(`${BACKEND}/${path}${search}`, { method: req.method, headers, body });
  } catch {
    return Response.json({ detail: 'The analysis engine is not reachable' }, { status: 502 });
  }

  // Stream through (incl. SSE and file downloads), copying the relevant headers.
  const out = new Headers();
  for (const h of ['content-type', 'content-disposition', 'cache-control']) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { handle as GET, handle as POST, handle as PUT, handle as DELETE };
