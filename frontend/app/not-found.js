import Link from 'next/link';
import { Compass } from 'lucide-react';

export const metadata = { title: 'Page not found', robots: { index: false } };

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-5 bg-[var(--background)] text-center px-6">
      <div className="w-12 h-12 rounded-xl bg-[oklch(0.2_0.05_250)] flex items-center justify-center">
        <Compass size={22} strokeWidth={1.5} className="text-[var(--accent)]" />
      </div>
      <div>
        <div className="text-[15px] font-semibold text-[var(--text)]">This page doesn&apos;t exist</div>
        <p className="text-[13px] text-[var(--muted)] max-w-[360px] mt-1.5 m-0">
          The link may be broken or the page may have moved.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/studio" className="inline-flex items-center px-4 py-2 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition">
          Go to the studio
        </Link>
        <Link href="/" className="text-[13px] text-[var(--muted)] hover:text-[var(--text)] transition">Home</Link>
      </div>
    </div>
  );
}
