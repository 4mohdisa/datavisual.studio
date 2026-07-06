import Link from 'next/link';
import {
  LayoutDashboard, Telescope, Cable, Sparkles, RefreshCw, FileDown,
  ArrowRight, MessagesSquare, ShieldCheck, Database, Globe, Users, Scale,
  Crown, FileText, MousePointerClick,
} from 'lucide-react';
import { DashboardMock, MetricBlock, MiniBars, MiniLine, MiniDonut, InsightBlock } from './Blocks';

const SECTION = 'max-w-[1120px] mx-auto px-6';

function FeatureCard({ icon: Icon, title, children }) {
  return (
    <div className="rounded-2xl border border-[var(--border-2)] bg-[var(--raised)] p-6 hover:border-[var(--border-3)] transition">
      <div className="w-10 h-10 rounded-lg bg-[oklch(0.2_0.05_250)] flex items-center justify-center mb-4">
        <Icon size={19} strokeWidth={1.5} className="text-[var(--accent)]" />
      </div>
      <div className="text-[15px] font-semibold text-[var(--text)] mb-1.5">{title}</div>
      <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0">{children}</p>
    </div>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="flex gap-4">
      <div className="shrink-0 w-8 h-8 rounded-full border border-[var(--accent)] text-[var(--accent)] flex items-center justify-center text-[13px] font-semibold">
        {n}
      </div>
      <div className="pb-8 border-l border-[var(--border)] pl-0 -ml-4 pl-8 last:pb-0">
        <div className="text-[14.5px] font-semibold text-[var(--text)] mb-1">{title}</div>
        <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0 max-w-[380px]">{children}</p>
      </div>
    </div>
  );
}

function CouncilNode({ icon: Icon, label, sub, accent }) {
  return (
    <div className={`rounded-xl border ${accent ? 'border-[var(--accent)]' : 'border-[var(--border-2)]'} bg-[var(--raised)] px-4 py-3 text-center`}>
      <Icon size={17} strokeWidth={1.5} className={`mx-auto mb-1.5 ${accent ? 'text-[var(--accent)]' : 'text-[var(--muted)]'}`} />
      <div className="text-[12.5px] font-semibold text-[var(--text)]">{label}</div>
      {sub && <div className="text-[10.5px] text-[var(--faint)] mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Landing() {
  return (
    <div className="h-screen overflow-y-auto bg-[var(--background)] text-[var(--text)]">
      {/* Nav */}
      <nav className="sticky top-0 z-40 border-b border-[var(--border)] bg-[oklch(0.12_0_0/0.8)] backdrop-blur">
        <div className={`${SECTION} h-[60px] flex items-center`}>
          <span className="text-[15.5px] font-semibold">datavisual.studio</span>
          <Link
            href="/studio"
            className="ml-auto inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition"
          >
            Open studio <ArrowRight size={14} strokeWidth={1.5} />
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <header className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(600px 320px at 20% 0%, oklch(0.30 0.09 250 / 0.35), transparent 70%),' +
              'radial-gradient(520px 300px at 85% 20%, oklch(0.28 0.09 300 / 0.28), transparent 70%)',
          }}
        />
        <div className={`${SECTION} relative grid grid-cols-1 lg:grid-cols-2 gap-12 items-center pt-20 pb-24`}>
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-[var(--border-2)] text-[11.5px] text-[var(--muted)] mb-6">
              <ShieldCheck size={12} strokeWidth={1.5} className="text-[#5ad08a]" />
              Free to use — bring your own AI keys, pay providers directly
            </div>
            <h1 className="text-[44px] lg:text-[54px] leading-[1.08] font-semibold tracking-tight m-0">
              Dashboards that{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#6aa8ff] to-[#b78aff]">
                track your situation
              </span>{' '}
              and tell you what changed
            </h1>
            <p className="text-[16px] text-[var(--muted)] leading-relaxed mt-5 max-w-[520px]">
              Connect your data and pin the questions that matter. One click keeps both
              your numbers and the live web in sync — and shows you exactly what moved
              since last time. Your data and the world, on one screen, always current.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-8">
              <Link
                href="/studio"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-sm font-medium hover:bg-[var(--new-chat-hover)] transition"
              >
                <LayoutDashboard size={16} strokeWidth={1.5} /> Open the studio
              </Link>
              <a
                href="#workflows"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md border border-[var(--border-2)] text-sm text-[var(--text)] hover:bg-[var(--active)] transition"
              >
                See how it works
              </a>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-2 mt-8 text-[12px] text-[var(--faint)]">
              <span>Live data + web research</span><span>·</span>
              <span>What-changed on every update</span><span>·</span>
              <span>4-model AI council</span><span>·</span>
              <span>Postgres / MySQL / SQLite / REST</span>
            </div>
          </div>
          <DashboardMock />
        </div>
      </header>

      {/* Features */}
      <section id="features" className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <h2 className="text-[28px] font-semibold m-0 mb-2">Everything between raw data and a decision</h2>
          <p className="text-[14px] text-[var(--muted)] m-0 mb-10">
            One tool for the dashboard work you'd do in a BI suite and the research you'd do in five browser tabs.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <FeatureCard icon={LayoutDashboard} title="Instant live dashboards">
              Metrics, interactive charts, entity comparison and a data table — generated from
              your columns in seconds, with five templates and a focus column. No AI cost.
            </FeatureCard>
            <FeatureCard icon={MessagesSquare} title="Edit by chat or by hand">
              "Add a pie of revenue by product" — or use the component gallery, form editors,
              reorder arrows and inline rename. Every edit updates the same dashboard in place.
            </FeatureCard>
            <FeatureCard icon={Telescope} title="Deep research, cited">
              Live web research plus four AI models that answer independently, peer-review each
              other anonymously, and get synthesised by a chairman into a report with sources.
            </FeatureCard>
            <FeatureCard icon={RefreshCw} title="One Update, and it tells you what changed">
              Hit <em>Update</em> and the dashboard re-pulls your live data and re-runs every
              pinned research topic — then shows a clear feed of what moved: which metrics
              shifted, by how much, and how many new sources appeared.
            </FeatureCard>
            <FeatureCard icon={Cable} title="Connect your database">
              PostgreSQL, MySQL, SQLite or any JSON REST API. Read-only imports, stored locally,
              so your dashboard always reflects the source — not a stale export.
            </FeatureCard>
            <FeatureCard icon={FileDown} title="Exports that hold up">
              Structured PDF or self-contained HTML — charts embedded as images, rendered
              markdown and cited sources. Share the file, keep the interactivity in the studio.
            </FeatureCard>
          </div>
        </div>
      </section>

      {/* Workflows */}
      <section id="workflows" className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <h2 className="text-[28px] font-semibold m-0 mb-10">Two workflows, one artifact</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            <div>
              <div className="flex items-center gap-2 mb-6">
                <LayoutDashboard size={18} strokeWidth={1.5} className="text-[var(--accent)]" />
                <span className="text-[17px] font-semibold">Build a dashboard</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[var(--faint)]">no AI cost</span>
              </div>
              <Step n="1" title="Bring data">
                Upload CSV / Excel / JSON, or connect a database with a read-only SQL query.
              </Step>
              <Step n="2" title="Generate">
                Pick a template — metrics, charts, comparison and table appear instantly,
                every widget rebuildable.
              </Step>
              <Step n="3" title="Refine">
                One-click prebuilt components, form editors, or just tell the assistant what
                you want. It understands "KPI cards" — typos included.
              </Step>
              <Step n="4" title="Stay current">
                Refresh re-pulls from your source and rebuilds every chart and metric —
                your edits survive.
              </Step>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-6">
                <Telescope size={18} strokeWidth={1.5} className="text-[oklch(0.75_0.15_150)]" />
                <span className="text-[17px] font-semibold">Deep research</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[var(--faint)]">~2 min</span>
              </div>
              <Step n="1" title="Ask anything">
                With or without a dataset attached. Watch every step live in the activity panel.
              </Step>
              <Step n="2" title="Web research + AI council">
                Three targeted web searches gather current facts, expert analysis and forecasts;
                four models analyse independently and peer-review anonymously.
              </Step>
              <Step n="3" title="Cited report">
                A chairman synthesises one calibrated answer — with sources, consensus level
                and prediction tables.
              </Step>
              <Step n="4" title="Dashboard, automatically">
                The findings, analytics and charts land on a live dashboard you keep editing
                and refreshing.
              </Step>
            </div>
          </div>
        </div>
      </section>

      {/* Council diagram */}
      <section id="council" className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <h2 className="text-[28px] font-semibold m-0 mb-2">How the AI council works</h2>
          <p className="text-[14px] text-[var(--muted)] m-0 mb-10 max-w-[640px]">
            One model can be confidently wrong. Four models answering independently, reviewing
            each other anonymously, and being synthesised by a chairman is much harder to fool.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 items-stretch mb-3">
            <CouncilNode icon={Users} label="4 council models" sub="answer independently" />
            <CouncilNode icon={Scale} label="Anonymous peer review" sub="rank each other's answers" />
            <CouncilNode icon={Crown} label="Chairman synthesis" sub="one calibrated answer" />
            <CouncilNode icon={FileText} label="Report + dashboard" sub="cited, editable, live" accent />
          </div>
          <div className="flex items-center gap-2 text-[11.5px] text-[var(--faint)]">
            <Globe size={13} strokeWidth={1.5} />
            Grounded by live web research injected before the council ever answers — with a
            deterministic prediction engine when your data carries ratings.
          </div>
        </div>
      </section>

      {/* Block components showcase */}
      <section id="blocks" className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <h2 className="text-[28px] font-semibold m-0 mb-2">Built from blocks</h2>
          <p className="text-[14px] text-[var(--muted)] m-0 mb-10 max-w-[640px]">
            Dashboards compose from typed widgets — metrics, nine chart types, research insight
            cards, comparison and tables. Add them by click, by form, or by sentence.
          </p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 items-start">
            <div className="flex flex-col gap-4">
              <MetricBlock label="Total revenue" value="3,852,180" delta="6.9% YoY" />
              <MetricBlock label="Council consensus" value="High" delta="4 models" />
            </div>
            <MiniBars title="Total revenue by region" />
            <MiniLine title="Revenue over time" />
            <div className="flex flex-col gap-4">
              <MiniDonut title="Share by product" />
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            <InsightBlock title="Internet research · 8 sources" lines={3} sources={['reuters.com', 'oecd.org', 'statista.com']} />
            <InsightBlock title="AI council synthesis" lines={3} sources={['4 models · consensus: high']} />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--border)] py-24 relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(600px 260px at 50% 100%, oklch(0.28 0.09 250 / 0.30), transparent 70%)' }}
        />
        <div className={`${SECTION} relative text-center`}>
          <h2 className="text-[32px] font-semibold m-0 mb-3">Your data has answers. Go get them.</h2>
          <p className="text-[14.5px] text-[var(--muted)] m-0 mb-8">
            Free to use — sign in and start building living dashboards in minutes.
          </p>
          <Link
            href="/studio"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[15px] font-medium hover:bg-[var(--new-chat-hover)] transition"
          >
            <MousePointerClick size={17} strokeWidth={1.5} /> Open the studio
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] py-8">
        <div className={`${SECTION} flex flex-col gap-3 text-[12px] text-[var(--faint)]`}>
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-[var(--muted)] font-medium">datavisual.studio</span>
            <span>Dashboards · Deep research · Data connectors</span>
            <span className="ml-auto inline-flex items-center gap-1.5">
              <Database size={12} strokeWidth={1.5} /> Free — your data stays on the platform's own server; AI runs on your keys.
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-[var(--border)]">
            <Link href="/privacy" className="hover:text-[var(--text)] transition">Privacy policy</Link>
            <Link href="/terms" className="hover:text-[var(--text)] transition">Terms of use</Link>
            <span className="ml-auto">
              Built by{' '}
              <a
                href="https://github.com/4mohdisa"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--muted)] hover:text-[var(--text)] underline underline-offset-2 transition"
              >
                Mohammed Isa
              </a>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
