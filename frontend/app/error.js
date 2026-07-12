'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';

// Route-level error boundary. Next renders this when a segment throws during
// render; `reset` re-attempts the segment.
export default function Error({ error, reset }) {
  useEffect(() => {
    api.logError?.({ message: error?.message || 'route error', stack: error?.stack });
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-5 bg-[var(--background)] text-center px-6">
      <div className="w-12 h-12 rounded-xl bg-[oklch(0.2_0.05_25)] flex items-center justify-center">
        <AlertTriangle size={22} strokeWidth={1.5} className="text-[var(--danger)]" />
      </div>
      <div>
        <div className="text-[15px] font-semibold text-[var(--text)]">Something went wrong</div>
        <p className="text-[13px] text-[var(--muted)] max-w-[380px] mt-1.5 m-0">
          This screen hit an unexpected error. Trying again usually fixes it.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => reset()} className="inline-flex items-center px-4 py-2 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition">
          Try again
        </button>
        <Link href="/studio" className="text-[13px] text-[var(--muted)] hover:text-[var(--text)] transition">Back to the studio</Link>
      </div>
    </div>
  );
}
