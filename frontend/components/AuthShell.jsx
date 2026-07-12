import Link from 'next/link';
import { ArrowLeft, ArrowRight, LayoutDashboard, Telescope, RefreshCw, Share2 } from 'lucide-react';

// Branded split layout for the Clerk sign-in / sign-up pages: product value on
// the left, the auth form on the right. Server component — the Clerk widget is
// passed in as children. On small screens the brand panel collapses.

const POINTS = [
  { icon: LayoutDashboard, text: 'Instant dashboards from any CSV, database or API' },
  { icon: Telescope, text: 'A council of AI models researches your question — cited' },
  { icon: RefreshCw, text: 'One update tells you exactly what changed' },
  { icon: Share2, text: 'Share a live, read-only link with anyone' },
];

// Shown in open dev mode (no Clerk key): the Clerk widget can't mount without a
// provider, and sign-in isn't required anyway, so point the visitor to the app.
export function OpenModeNote() {
  return (
    <div className="w-full rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-6 text-center">
      <div className="text-[15px] font-medium text-[var(--text)] mb-1.5">Authentication is off</div>
      <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0 mb-5">
        This environment runs in open mode — no sign-in needed. Add Clerk keys to enable
        accounts. For now, head straight into the studio.
      </p>
      <Link
        href="/studio"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-sm font-medium hover:bg-[var(--new-chat-hover)] transition"
      >
        Open the studio <ArrowRight size={15} strokeWidth={1.5} />
      </Link>
    </div>
  );
}

export default function AuthShell({ children, mode }) {
  const isSignUp = mode === 'sign-up';
  return (
    <div className="min-h-screen flex bg-[var(--background)] text-[var(--text)]">
      {/* Brand panel */}
      <aside className="hidden lg:flex flex-col justify-between w-[45%] max-w-[560px] p-12 relative overflow-hidden border-r border-[var(--border)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(560px 320px at 15% 0%, oklch(0.30 0.09 250 / 0.40), transparent 70%),' +
              'radial-gradient(480px 300px at 90% 100%, oklch(0.28 0.09 300 / 0.30), transparent 70%)',
          }}
        />
        <Link href="/" className="relative text-[16px] font-semibold hover:opacity-80 transition">
          datavisual.studio
        </Link>

        <div className="relative">
          <h1 className="text-[30px] font-semibold leading-[1.15] tracking-tight text-balance mb-7 max-w-[380px]">
            {isSignUp
              ? 'Turn your data into living dashboards'
              : 'Welcome back to your workspace'}
          </h1>
          <ul className="flex flex-col gap-4 m-0 p-0 list-none">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-[14px] text-[var(--muted)]">
                <span className="shrink-0 mt-0.5 w-7 h-7 rounded-lg bg-[oklch(0.20_0.04_250)] flex items-center justify-center">
                  <Icon size={15} strokeWidth={1.5} className="text-[var(--accent)]" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-[12px] text-[var(--faint)] m-0">
          Free · bring your own AI keys · your data stays on the platform&apos;s own server
        </p>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-[420px] flex flex-col items-center gap-6">
          <Link
            href="/"
            className="self-start inline-flex items-center gap-1.5 text-[13px] text-[var(--muted)] hover:text-[var(--text)] transition lg:hidden"
          >
            <ArrowLeft size={15} strokeWidth={1.5} /> Home
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}
