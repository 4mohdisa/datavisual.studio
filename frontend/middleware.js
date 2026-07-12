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
      const p = req.nextUrl.pathname;
      // Admin (password-gated on the backend) and public share views need no
      // Clerk session — the backend checks the password / share token itself.
      // Only exempt CLEAN paths: an encoded slash (%2f) or a `..` segment could
      // otherwise smuggle the exemption onto an identity-scoped endpoint.
      const exemptPrefix = p.startsWith('/api/backend/api/admin') || p.startsWith('/api/backend/api/public/');
      if (exemptPrefix && !p.includes('%') && !p.includes('..')) return;
      if (isProtectedRoute(req)) await auth.protect();
    })
  : () => NextResponse.next();

export const config = {
  matcher: ['/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)', '/(api|trpc)(.*)'],
};
