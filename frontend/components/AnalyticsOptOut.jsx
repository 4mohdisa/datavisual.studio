'use client';

import { useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { analyticsOptedOut, setAnalyticsOptOut } from '../lib/analytics';

// The analytics opt-out control (Launch Phase 4b), rendered on the privacy page.
// Reflects the effective state (explicit choice OR Global Privacy Control) and
// lets the visitor turn first-party analytics off. Client-only — the stored flag
// lives in this browser.
export default function AnalyticsOptOut() {
  const [out, setOut] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => { setOut(analyticsOptedOut()); setReady(true); }, []);

  const toggle = () => {
    const next = !out;
    setAnalyticsOptOut(next);
    setOut(next);
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={toggle}
        aria-pressed={out}
        className="inline-flex items-center gap-2 rounded-md border border-[var(--border-2)] px-3.5 py-2 text-[13px] text-[var(--text)] hover:bg-[var(--active)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] transition"
      >
        {out
          ? <><X size={14} strokeWidth={2} className="text-[var(--danger)]" /> Product analytics are off in this browser</>
          : <><Check size={14} strokeWidth={2} className="text-[#5ad08a]" /> Product analytics are on — turn them off</>}
      </button>
      <span className="text-[12px] text-[var(--faint)]">{ready ? 'Your choice is saved in this browser.' : ''}</span>
    </div>
  );
}
