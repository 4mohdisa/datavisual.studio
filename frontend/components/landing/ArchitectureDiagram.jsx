import { Globe, Server, Database, Shield } from 'lucide-react';

// The request path, as a diagram (Launch Phase 2, "How it's built"). Real text
// nodes + connectors — accessible and responsive (a row on desktop, a column on
// mobile). A subtle dot travels the connectors to read as "a request flowing";
// the global prefers-reduced-motion backstop settles it. The whole figure has a
// text alternative in its <figcaption>.

const NODES = [
  { icon: Globe, label: 'Browser', sub: "A stranger's device", tone: 'var(--muted)' },
  { icon: Shield, label: 'Next.js proxy', sub: 'Vercel · verifies the session', tone: 'var(--accent)' },
  { icon: Server, label: 'FastAPI', sub: 'AWS · the engine', tone: '#6aa8ff' },
  { icon: Database, label: 'data/ · JSON', sub: 'local disk · the whole DB', tone: '#5ad08a' },
];

function Connector() {
  // Static line: vertical between stacked nodes on mobile, horizontal on desktop.
  return (
    <div
      aria-hidden="true"
      className="mx-auto h-5 w-px bg-gradient-to-b from-[var(--border-2)] to-[var(--border-3)] lg:mx-0 lg:h-px lg:w-12 lg:bg-gradient-to-r shrink-0 self-center"
    />
  );
}

export default function ArchitectureDiagram() {
  return (
    <figure className="m-0">
      <div className="flex flex-col items-stretch lg:flex-row lg:items-center lg:justify-between rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5 sm:p-6">
        {NODES.map((n, i) => (
          <div key={n.label} className="contents">
            <div className="flex items-center gap-3 lg:flex-col lg:gap-2 lg:text-center lg:flex-1">
              <span
                className="shrink-0 grid place-items-center w-10 h-10 rounded-lg border border-[var(--border-2)] bg-[var(--background)]"
                style={{ color: n.tone }}
              >
                <n.icon size={18} strokeWidth={1.5} />
              </span>
              <span className="min-w-0">
                <span className="block text-[13.5px] font-semibold text-[var(--text)]">{n.label}</span>
                <span className="block text-[11.5px] text-[var(--faint)]">{n.sub}</span>
              </span>
            </div>
            {i < NODES.length - 1 && <Connector />}
          </div>
        ))}
      </div>
      <figcaption className="sr-only">
        Request path: the browser talks only to a Next.js proxy on Vercel, which verifies the Clerk
        session and forwards to a FastAPI backend on AWS, which keeps all state as JSON files on local
        disk — there is no separate database.
      </figcaption>
    </figure>
  );
}
