'use client';

import { useEffect } from 'react';
import { useUser } from '@clerk/nextjs';
import { track, identify } from '../lib/analytics';

// The anon → user stitch (1c). Once per user per browser: link the first-party
// anon_id to the account, and emit signup_completed for a brand-new account.
// Only mounted when Clerk is configured (needs a ClerkProvider ancestor).
export default function Identify() {
  const { isSignedIn, user } = useUser();
  useEffect(() => {
    if (!isSignedIn || !user?.id) return;
    try {
      const key = 'dv_identified_' + user.id;
      if (localStorage.getItem(key)) return;
      localStorage.setItem(key, '1');
      identify(user.id);
      const createdMs = user.createdAt ? new Date(user.createdAt).getTime() : 0;
      // Account created in the last 5 min → this browser just completed signup.
      if (createdMs && Date.now() - createdMs < 5 * 60 * 1000) {
        track('signup_completed', { user_id: user.id });
      }
    } catch { /* analytics must never break the app */ }
  }, [isSignedIn, user?.id]);
  return null;
}
