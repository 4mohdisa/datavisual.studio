import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

// The landing page (/), legal pages and sign-in/up stay public; the product
// is protected. /admin is NOT Clerk-protected — it's gated by ADMIN_PASSWORD
// on the backend instead.
const isProtectedRoute = createRouteMatcher([
  '/studio(.*)',
  '/chat(.*)',
  '/dashboard(.*)',
  '/api/backend(.*)',
]);

const authEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

// OPEN mode (no Clerk keys yet): pass everything through so the app stays
// usable in development. The moment keys are configured, protection is on.
export default authEnabled
  ? clerkMiddleware(async (auth, req) => {
      // Admin API calls carry the password header; the backend checks it.
      if (req.nextUrl.pathname.startsWith('/api/backend/api/admin')) return;
      if (isProtectedRoute(req)) await auth.protect();
    })
  : () => NextResponse.next();

export const config = {
  matcher: ['/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)', '/(api|trpc)(.*)'],
};
