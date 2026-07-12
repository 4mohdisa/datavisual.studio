// Mints a short-lived, single-use HMAC upload ticket so the browser can POST a
// large file DIRECTLY to the backend origin (bypassing the serverless proxy's
// body-size limit). Signed with PROXY_SHARED_SECRET; the backend verifies it.
// Only issued to an authenticated user. Returns 501 when direct upload isn't
// configured (single-box deploys keep using the proxied /api/upload).
import { auth } from '@clerk/nextjs/server';
import crypto from 'crypto';

export const dynamic = 'force-dynamic';

const SECRET = process.env.PROXY_SHARED_SECRET;
const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN;
const AUTH_ENABLED = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export async function POST() {
  if (!SECRET || !BACKEND_ORIGIN) {
    return Response.json({ detail: 'Direct upload is not configured' }, { status: 501 });
  }
  let userId = 'devuser';
  if (AUTH_ENABLED) {
    const { userId: uid } = await auth();
    if (!uid) return Response.json({ detail: 'Sign in to continue' }, { status: 401 });
    userId = uid;
  }
  const exp = Math.floor(Date.now() / 1000) + 300; // 5-minute TTL
  const nonce = crypto.randomUUID().replace(/-/g, '');
  const mac = crypto.createHmac('sha256', SECRET).update(`${userId}.${exp}.${nonce}`).digest('hex');
  return Response.json({ ticket: `${userId}.${exp}.${nonce}.${mac}`, backend_origin: BACKEND_ORIGIN });
}
