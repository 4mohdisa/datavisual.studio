'use client';

import Link from 'next/link';
import { ArrowRight, Eye, LayoutDashboard } from 'lucide-react';
import DashboardWidgets, { relativeTime } from './DashboardWidgets';

// Public, read-only render of a shared dashboard. Reuses the exact same widget
// renderer as the editor (DashboardWidgets) but passes no handlers, so nothing
// is editable. Server component (app/share/[shareId]/page.js) fetches the data
// and passes it in, so this paints immediately and unfurls with real metadata.

export default function SharedView({ data }) {
  if (!data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-[var(--background)] text-center px-6">
        <div className="w-11 h-11 rounded-xl bg-[oklch(0.2_0.05_250)] flex items-center justify-center">
          <Eye size={19} strokeWidth={1.5} className="text-[var(--accent)]" />
        </div>
        <div className="text-[15px] font-medium text-[var(--text)]">This shared link is unavailable</div>
        <p className="text-[13px] text-[var(--muted)] max-w-[360px] m-0">
          The link may have been revoked, or it never existed. Ask whoever shared it for an updated link.
        </p>
        <Link href="/" className="text-[13px] text-[var(--accent)] hover:underline">Go to datavisual.studio →</Link>
      </div>
    );
  }

  const widgets = data.dashboard?.widgets || [];

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--text)] overflow-y-auto">
      {/* Top bar — brand + read-only badge + build-your-own CTA */}
      <div className="sticky top-0 z-40 border-b border-[var(--border)] bg-[oklch(0.12_0_0/0.85)] backdrop-blur">
        <div className="max-w-[1400px] mx-auto px-6 h-[56px] flex items-center gap-3">
          <Link href="/" className="shrink-0 text-[14.5px] font-semibold hover:opacity-80 transition">datavisual.studio</Link>
          {/* Badge is secondary — drop it on the narrowest screens so the brand
              and CTA always fit on one line. */}
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[11px] text-[var(--muted)]">
            <Eye size={11} strokeWidth={1.5} /> {data.is_demo ? 'Live demo · sample data' : 'Read-only shared view'}
          </span>
          <Link
            href="/studio"
            className="ml-auto shrink-0 whitespace-nowrap inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition"
          >
            Build your own <ArrowRight size={14} strokeWidth={1.5} />
          </Link>
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-6 py-6 flex flex-col gap-6">
        <div className="flex items-center gap-3 flex-wrap">
          <LayoutDashboard size={20} strokeWidth={1.5} className="text-[var(--accent)]" />
          <h1 className="text-[22px] font-semibold m-0">{data.title || 'Dashboard'}</h1>
          {data.dashboard?.last_synced && (
            <span className="text-[12px] text-[var(--faint)]">
              Updated {relativeTime(data.dashboard.last_synced)}
            </span>
          )}
        </div>

        {widgets.length === 0 ? (
          <div className="text-[var(--muted)] text-sm">This shared dashboard has no widgets yet.</div>
        ) : (
          <DashboardWidgets widgets={widgets} dataset={data.dataset} />
        )}

        {/* Footer CTA */}
        <div className="mt-6 flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border border-[var(--border-2)] bg-[oklch(0.16_0.02_250)] p-5">
          <div className="flex-1">
            <div className="text-[15px] font-semibold text-[var(--text)] mb-1">Made with datavisual.studio</div>
            <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0">
              Turn any dataset into a live dashboard, then let a council of AI models research
              your question on the web. Free — bring your own AI keys.
            </p>
          </div>
          <Link
            href="/studio"
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-sm font-medium hover:bg-[var(--new-chat-hover)] transition"
          >
            <LayoutDashboard size={16} strokeWidth={1.5} /> Open the studio
          </Link>
        </div>
      </div>
    </div>
  );
}
