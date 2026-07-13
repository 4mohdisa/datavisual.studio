'use client';

import { useEffect } from 'react';
import { track } from '../lib/analytics';

// Demo funnel events (1c): a view on mount, and a single interact on the first
// pointer interaction — the signal that the visitor actually engaged.
export default function DemoTracker() {
  useEffect(() => {
    track('demo_view');
    let fired = false;
    const onInteract = () => {
      if (fired) return;
      fired = true;
      track('demo_interact');
      window.removeEventListener('pointerdown', onInteract);
    };
    window.addEventListener('pointerdown', onInteract, { passive: true });
    return () => window.removeEventListener('pointerdown', onInteract);
  }, []);
  return null;
}
