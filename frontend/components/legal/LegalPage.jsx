import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

// Shared shell for /privacy and /terms: landing-style nav, readable measure,
// footer with the cross-link back. Server component — no client JS needed.
export default function LegalPage({ title, updated, children }) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--text)]">
      <nav className="sticky top-0 z-40 border-b border-[var(--border)] bg-[oklch(0.12_0_0/0.8)] backdrop-blur">
        <div className="max-w-[760px] mx-auto px-6 h-[60px] flex items-center">
          <Link href="/" className="text-[15.5px] font-semibold hover:opacity-80 transition">
            datavisual.studio
          </Link>
          <Link
            href="/studio"
            className="ml-auto inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition"
          >
            Open studio <ArrowRight size={14} strokeWidth={1.5} />
          </Link>
        </div>
      </nav>

      <main id="main-content" tabIndex={-1} className="max-w-[760px] mx-auto px-6 py-14 legal-content outline-none">
        <h1 className="text-[32px] font-semibold m-0 mb-2">{title}</h1>
        <p className="text-[12.5px] text-[var(--faint)] m-0 mb-10">Last updated: {updated}</p>
        {children}
      </main>

      <footer className="border-t border-[var(--border)] py-8">
        <div className="max-w-[760px] mx-auto px-6 flex flex-wrap items-center gap-4 text-[12px] text-[var(--faint)]">
          <Link href="/privacy" className="hover:text-[var(--text)] transition">Privacy policy</Link>
          <Link href="/terms" className="hover:text-[var(--text)] transition">Terms of use</Link>
          <Link href="/about" className="hover:text-[var(--text)] transition">About</Link>
          <span className="ml-auto">
            Built by{' '}
            <a
              href="https://isaxcode.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--muted)] hover:text-[var(--text)] underline underline-offset-2 transition"
            >
              Mohammed Isa
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}

// Section helpers keep the page files to pure content.
export function Section({ title, children }) {
  return (
    <section className="mb-8">
      <h2 className="text-[18px] font-semibold m-0 mb-3">{title}</h2>
      <div className="text-[14px] text-[var(--muted)] leading-relaxed flex flex-col gap-3">{children}</div>
    </section>
  );
}
