import Link from 'next/link';
import {
  LayoutDashboard, Telescope, Cable, RefreshCw, FileDown, ArrowRight,
  MessagesSquare, ShieldCheck, Database, Share2, Sliders, Table2,
  Users, LineChart, Building2, FlaskConical, MousePointerClick, Star,
  Calculator, KeyRound, Scale, HardDrive, Check,
} from 'lucide-react';

const REPO_URL = 'https://github.com/4mohdisa/datavisual.studio';
import Reveal from './Reveal';
import HeroReplay from './HeroReplay';
import Track from '../Track';
import { LiveMonitorDemo, BuildDemo, ChatEditDemo, CouncilDemo } from './FeatureDemos';
import ArchitectureDiagram from './ArchitectureDiagram';
import { Stack, Row, Grid } from '../ui/layout';

// The engineering decisions, written as reasoning — this is the portfolio
// section. Each item leads with the decision, then WHY it was made that way.
const DECISIONS = [
  {
    icon: Calculator,
    title: 'The model never does arithmetic',
    body: 'The LLM turns your question into a JSON query spec; a deterministic Python engine executes it and phrases the answer from the result. Nothing about a number is left to the model — so every figure the product shows can be defended, because a person or a test can re-derive it.',
  },
  {
    icon: ShieldCheck,
    title: 'Numbers fail closed',
    body: 'Every figure in an answer must appear in the computed result or be a derivation the answer shows its working for — otherwise it refuses rather than guess. A level like MRR is never summed across time; “total customers in June” aggregates across plans, not one of them.',
  },
  {
    icon: KeyRound,
    title: 'Your keys, never mine',
    body: 'Users bring their own AI keys, encrypted at rest and resolved per request from the signed-in identity. The owner’s key is never spent on someone else’s request — so the product can be free without a metered bill in the middle.',
  },
  {
    icon: Users,
    title: 'A council, not one oracle',
    body: 'For research, several models answer independently, review each other’s answers anonymously, and a chairman synthesises one cited report. No single model’s confidence is load-bearing, and a model that quietly drops out is surfaced, not hidden.',
  },
  {
    icon: HardDrive,
    title: 'No database, on purpose',
    body: 'All state is JSON on disk. For a single-tenant, single-replica product that removes migrations, a connection pool and a second backup target — and makes the security model tractable: one directory is the trust boundary, one function is the id check.',
  },
  {
    icon: Scale,
    title: 'Accessible by construction',
    body: 'Charts carry a text alternative generated from the plotted numbers (not the LLM) and a “view as table” toggle; overlays trap and restore focus; contrast meets WCAG AA. axe runs on every route in CI. The a11y is in the components, not bolted on after.',
  },
];

const SECTION = 'max-w-[1120px] mx-auto px-6';

// One alternating feature row: an animated demo on one side, the pitch on the
// other. Breaks the "identical card grid" reflex — each row is its own scene.
function ShowcaseRow({ demo, icon: Icon, kicker, title, children, flip }) {
  return (
    <Reveal className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-14 items-center">
      <div className={flip ? 'lg:order-2' : ''}>
        <div className="flex items-center gap-2 mb-3 text-[var(--accent)]">
          <Icon size={18} strokeWidth={1.5} />
          <span className="text-[12.5px] font-medium">{kicker}</span>
        </div>
        <h3 className="text-[24px] lg:text-[27px] font-semibold text-[var(--text)] m-0 mb-3 tracking-tight text-balance">{title}</h3>
        <div className="text-[14.5px] text-[var(--muted)] leading-relaxed max-w-[440px]">{children}</div>
      </div>
      <div className={flip ? 'lg:order-1' : ''}>{demo}</div>
    </Reveal>
  );
}

function MiniFeature({ icon: Icon, title, children }) {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 w-9 h-9 rounded-lg bg-[oklch(0.18_0.03_250)] flex items-center justify-center">
        <Icon size={17} strokeWidth={1.5} className="text-[var(--accent)]" />
      </div>
      <div>
        <div className="text-[14px] font-semibold text-[var(--text)] mb-0.5">{title}</div>
        <p className="text-[12.5px] text-[var(--muted)] leading-relaxed m-0">{children}</p>
      </div>
    </div>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="flex gap-4">
      <div className="shrink-0 w-8 h-8 rounded-full border border-[var(--accent)] text-[var(--accent)] flex items-center justify-center text-[13px] font-semibold">{n}</div>
      <div className="pb-8 border-l border-[var(--border)] -ml-4 pl-8 last:pb-0 last:border-l-0">
        <div className="text-[14.5px] font-semibold text-[var(--text)] mb-1">{title}</div>
        <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0 max-w-[380px]">{children}</p>
      </div>
    </div>
  );
}

const USE_CASES = [
  { icon: LineChart, title: 'Analysts', body: 'Skip the BI-tool setup — a full dashboard from a CSV or query in seconds, then refine it in plain English.' },
  { icon: Building2, title: 'Founders & operators', body: 'Watch the metrics that matter and the market around them; one Update tells you what moved since yesterday.' },
  { icon: FlaskConical, title: 'Researchers', body: 'Ask a hard question and get a cited, multi-model report grounded in live web research — not one model’s guess.' },
  { icon: Users, title: 'Teams', body: 'Share a live, read-only link so anyone can see the dashboard — no seats, no sign-in, no exposed keys.' },
];

const FAQ = [
  { q: 'Is datavisual.studio really free?', a: 'Yes. The app is free — you bring your own AI provider keys (OpenRouter, and optionally Google Gemini) and pay those providers directly for usage. We never bill you, and your keys are only ever sent to the AI providers themselves.' },
  { q: 'What data can I connect?', a: 'Upload a CSV, Excel or JSON file, or connect a SQL database (PostgreSQL, MySQL, SQLite) or any JSON REST API. Database imports are read-only, and your dashboard can re-pull from the source anytime.' },
  { q: 'How is this different from a normal BI tool?', a: 'Dashboards are editable by chat and by hand, and they don’t just display your numbers. One “Update” re-pulls your data and re-runs the research questions you pinned, then shows a clear feed of exactly what changed since last time.' },
  { q: 'What is the AI research council?', a: 'Instead of trusting one model, several AI models answer your question independently, review each other’s answers anonymously, and a chairman model synthesises a single cited report — grounded in live web search.' },
  { q: 'Can I share a dashboard or report?', a: 'Yes. Any dashboard or research report can be shared as a public, read-only link. Viewers can explore the charts and data but can’t edit anything, and your data source and AI keys are never exposed.' },
  { q: 'Where is my data stored?', a: 'On the platform’s own server, on local disk — there is no third-party database. Your datasets, dashboards and reports are private to your account and are never sold or shared.' },
];

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ.map((f) => ({
    '@type': 'Question',
    name: f.q,
    acceptedAnswer: { '@type': 'Answer', text: f.a },
  })),
};

// HowTo structured data for the build-a-dashboard workflow (the "how you use it"
// section) — keeps SoftwareApplication (layout) and FAQPage (above) alongside it.
const howToJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'HowTo',
  name: 'Build a living dashboard from your data',
  description: 'Turn a file or database into an editable dashboard, then keep it in sync with your data and the live web.',
  step: [
    { '@type': 'HowToStep', position: 1, name: 'Bring data', text: 'Upload a CSV, Excel or JSON file, or connect a SQL database or REST API with a read-only query.' },
    { '@type': 'HowToStep', position: 2, name: 'Generate', text: 'Pick a template — metrics, charts, comparison and a data table appear instantly, every widget rebuildable.' },
    { '@type': 'HowToStep', position: 3, name: 'Refine', text: 'Edit by chat or by hand — add, change or remove widgets; the assistant applies your edits in place.' },
    { '@type': 'HowToStep', position: 4, name: 'Monitor', text: 'Hit Update to re-pull the source and re-run pinned research, then see exactly what changed since last time.' },
  ],
};

export default function Landing() {
  return (
    <div className="h-screen overflow-y-auto bg-[var(--background)] text-[var(--text)]">
      <Track event="landing_view" />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(howToJsonLd) }} />

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
          className="dv-drift pointer-events-none absolute inset-0"
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
            <h1 className="text-[44px] lg:text-[54px] leading-[1.08] font-semibold tracking-tight m-0 text-balance">
              Dashboards that{' '}
              <span className="text-[#6aa8ff]">track your situation</span>{' '}
              and tell you what changed
            </h1>
            <p className="text-[16px] text-[var(--muted)] leading-relaxed mt-5 max-w-[520px]">
              Connect your data and pin the questions that matter. One click keeps both
              your numbers and the live web in sync — and shows you exactly what moved
              since last time. Your data and the world, on one screen, always current.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-8">
              <Link
                href="/demo"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-sm font-medium hover:bg-[var(--new-chat-hover)] transition"
              >
                <LayoutDashboard size={16} strokeWidth={1.5} /> See a live dashboard
              </Link>
              <Link
                href="/studio"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md border border-[var(--border-2)] text-sm text-[var(--text)] hover:bg-[var(--active)] transition"
              >
                Open the studio
              </Link>
            </div>
            <div className="text-[12px] text-[var(--faint)] mt-2.5">The demo is a real dashboard — no sign-up, no AI key. Opens instantly.</div>
            <div className="flex flex-wrap gap-x-6 gap-y-2 mt-8 text-[12px] text-[var(--faint)]">
              <span>Live data + web research</span><span>·</span>
              <span>What-changed on every update</span><span>·</span>
              <span>Multi-model AI council</span><span>·</span>
              <span>Postgres / MySQL / SQLite / REST</span>
            </div>
          </div>
          <div className="dv-drift" style={{ animationDelay: '1.5s' }}>
            <HeroReplay />
          </div>
        </div>
      </header>

      {/* The problem — the gap the product exists to close */}
      <section className="border-t border-[var(--border)] py-20">
        <div className={`${SECTION} grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-10 lg:gap-16 items-center`}>
          <Reveal>
            <h2 className="text-[28px] lg:text-[32px] font-semibold m-0 tracking-tight text-balance">
              A dashboard tells you what happened.<br className="hidden sm:block" />{' '}
              <span className="text-[var(--muted)]">Nothing tells you what changed.</span>
            </h2>
            <p className="text-[15px] text-[var(--muted)] leading-relaxed mt-5 max-w-[520px]">
              So you build the dashboard once, then re-check it by hand — reload the data, re-run the
              same searches, try to remember last week’s numbers. The moment that actually matters —
              the number that moved, the source that appeared — is the one you find out about late.
            </p>
            <p className="text-[15px] text-[var(--text)] leading-relaxed mt-4 max-w-[520px]">
              datavisual.studio keeps your data <em className="not-italic font-medium">and</em> the live
              web in sync behind one dashboard, and leads with the delta: what moved, by how much, and
              what’s new — since the last time you looked.
            </p>
          </Reveal>
          <Reveal delay={80}>
            <Stack gap="sm" className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5">
              <div className="text-[11.5px] font-medium uppercase tracking-wide text-[var(--faint)]">Since your last visit</div>
              <Row justify="between" className="text-[14px]">
                <span className="text-[var(--muted)]">Revenue</span>
                <span className="tabular-nums text-[var(--text)]">3.43M → 3.85M <span className="text-[#5ad08a]">▲ 12.4%</span></span>
              </Row>
              <Row justify="between" className="text-[14px]">
                <span className="text-[var(--muted)]">Churn</span>
                <span className="tabular-nums text-[var(--text)]">2.1% → 2.6% <span className="text-[#f0776a]">▲ 0.5pt</span></span>
              </Row>
              <Row justify="between" className="text-[14px]">
                <span className="text-[var(--muted)]">Pinned research</span>
                <span className="tabular-nums text-[var(--text)]">3 new sources</span>
              </Row>
              <div className="text-[12px] text-[var(--faint)] pt-1 border-t border-[var(--border)] mt-1">
                Illustrative — this is what an <span className="text-[var(--muted)]">Update</span> surfaces.
              </div>
            </Stack>
          </Reveal>
        </div>
      </section>

      {/* Feature showcase — alternating animated rows */}
      <section id="how" className="border-t border-[var(--border)] py-20">
        <div className={`${SECTION} mb-14`}>
          <Reveal>
            <h2 className="text-[28px] lg:text-[32px] font-semibold m-0 mb-2 tracking-tight text-balance">Everything between raw data and a decision</h2>
            <p className="text-[14.5px] text-[var(--muted)] m-0 max-w-[560px]">
              The dashboard work you’d do in a BI suite and the research you’d do in five browser tabs — in one place, and alive.
            </p>
          </Reveal>
        </div>
        <div className={`${SECTION} flex flex-col gap-20`}>
          <ShowcaseRow
            demo={<LiveMonitorDemo />}
            icon={RefreshCw}
            kicker="The living monitor"
            title="One update, and it tells you what changed"
          >
            Pin the metrics and research questions you care about. Hit <em className="text-[var(--text)] not-italic font-medium">Update</em> and
            the dashboard re-pulls your live data <span className="text-[var(--text)]">and</span> re-runs every pinned topic — then
            hands you a plain-English feed of what moved, by how much, and which new sources appeared.
          </ShowcaseRow>

          <ShowcaseRow
            demo={<BuildDemo />}
            icon={LayoutDashboard}
            kicker="Instant dashboards"
            title="A full dashboard from your data in seconds"
            flip
          >
            Metrics, interactive charts, entity comparison and a searchable data table — generated from your
            columns in one click, no AI cost. Five templates and a focus column shape the first draft; every
            widget is fully rebuildable.
          </ShowcaseRow>

          <ShowcaseRow
            demo={<ChatEditDemo />}
            icon={MessagesSquare}
            kicker="Edit by chat or by hand"
            title="“Add a pie of revenue by product.” Done."
          >
            Talk to the dashboard assistant, or use the component gallery, form editors and reorder controls.
            Every edit updates the same dashboard in place — it understands what you mean, typos and all.
          </ShowcaseRow>

          <ShowcaseRow
            demo={<CouncilDemo />}
            icon={Telescope}
            kicker="Deep research, cited"
            title="A council of AI models, not one confident guess"
            flip
          >
            One model can be confidently wrong. Here, several models answer independently, review each other
            anonymously, and a chairman synthesises one cited report — grounded in live web research before
            it ever answers. The findings land straight on a dashboard.
          </ShowcaseRow>
        </div>
      </section>

      {/* Secondary features — compact, varied (not another big-card grid) */}
      <section className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <Reveal>
            <h2 className="text-[24px] font-semibold m-0 mb-10 tracking-tight">And everything around it</h2>
          </Reveal>
          <Reveal className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-10 gap-y-8">
            <MiniFeature icon={Cable} title="Connect your database">
              PostgreSQL, MySQL, SQLite or any JSON REST API — read-only, so the dashboard reflects the source, not a stale export.
            </MiniFeature>
            <MiniFeature icon={Share2} title="Share as a link">
              Turn any dashboard or report into a public, read-only link. No sign-in for viewers; your data source and keys stay private.
            </MiniFeature>
            <MiniFeature icon={FileDown} title="Exports that hold up">
              Structured PDF or self-contained HTML — charts embedded as images, rendered markdown and cited sources.
            </MiniFeature>
            <MiniFeature icon={Sliders} title="Templates & focus">
              Minimal, Overview, Full, KPI or Visual — then pick the column the headline metric and first charts revolve around.
            </MiniFeature>
            <MiniFeature icon={Table2} title="Live data table">
              Every dataset comes with a searchable, sortable, paginated table and one-click CSV download.
            </MiniFeature>
            <MiniFeature icon={LineChart} title="Prediction engine">
              When your data carries ratings, a deterministic ELO / Poisson / XGBoost engine adds calibrated forecasts.
            </MiniFeature>
          </Reveal>
        </div>
      </section>

      {/* Use cases */}
      <section className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <Reveal>
            <h2 className="text-[24px] font-semibold m-0 mb-2 tracking-tight">Built for anyone who asks their data questions</h2>
            <p className="text-[14px] text-[var(--muted)] m-0 mb-10 max-w-[540px]">One tool that flexes from a quick chart to a fully-monitored, cited research board.</p>
          </Reveal>
          <Reveal className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {USE_CASES.map((u) => (
              <div key={u.title} className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5">
                <u.icon size={18} strokeWidth={1.5} className="text-[var(--accent)] mb-3" />
                <div className="text-[14.5px] font-semibold text-[var(--text)] mb-1.5">{u.title}</div>
                <p className="text-[12.5px] text-[var(--muted)] leading-relaxed m-0">{u.body}</p>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* Workflows — a real ordered sequence, so the numbers earn their place */}
      <section className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <Reveal>
            <h2 className="text-[28px] font-semibold m-0 mb-10 tracking-tight">Two workflows, one living artifact</h2>
          </Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            <Reveal>
              <div className="flex items-center gap-2 mb-6">
                <LayoutDashboard size={18} strokeWidth={1.5} className="text-[var(--accent)]" />
                <span className="text-[17px] font-semibold">Build a dashboard</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[var(--faint)]">no AI cost</span>
              </div>
              <Step n="1" title="Bring data">Upload CSV / Excel / JSON, or connect a database with a read-only query.</Step>
              <Step n="2" title="Generate">Pick a template — metrics, charts, comparison and table appear instantly, every widget rebuildable.</Step>
              <Step n="3" title="Refine">One-click components, form editors, or just tell the assistant what you want.</Step>
              <Step n="4" title="Monitor">Hit Update to re-pull the source and see what changed — your edits survive.</Step>
            </Reveal>
            <Reveal delay={80}>
              <div className="flex items-center gap-2 mb-6">
                <Telescope size={18} strokeWidth={1.5} className="text-[oklch(0.75_0.15_150)]" />
                <span className="text-[17px] font-semibold">Deep research</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[var(--faint)]">~2 min</span>
              </div>
              <Step n="1" title="Ask anything">With or without a dataset attached. Watch every step live.</Step>
              <Step n="2" title="Web + council">Targeted web searches gather current facts; multiple models analyse and peer-review anonymously.</Step>
              <Step n="3" title="Cited report">A chairman synthesises one calibrated answer — sources, consensus and prediction tables.</Step>
              <Step n="4" title="Becomes a dashboard">The findings, analytics and charts land on a live dashboard you keep editing and monitoring.</Step>
            </Reveal>
          </div>
        </div>
      </section>

      {/* How it's built — the portfolio section: architecture + the reasoning */}
      <section id="how-its-built" className="border-t border-[var(--border)] py-20">
        <div className={SECTION}>
          <Reveal>
            <h2 className="text-[28px] lg:text-[32px] font-semibold m-0 mb-3 tracking-tight text-balance">How it’s built</h2>
            <p className="text-[14.5px] text-[var(--muted)] leading-relaxed m-0 max-w-[620px]">
              This one’s for the engineers. The interesting part of this product isn’t the feature list —
              it’s the constraints it holds so the numbers can be trusted. A stranger’s browser talks to
              a thin Next.js proxy, which is the only thing that reaches the FastAPI backend; all state is
              JSON on disk.
            </p>
          </Reveal>

          <Reveal delay={60} className="mt-10">
            <ArchitectureDiagram />
            <p className="text-[12.5px] text-[var(--faint)] mt-3 text-center lg:text-left">
              <span className="font-mono text-[var(--muted)]">Next.js 16 · React 19</span> on Vercel ·{' '}
              <span className="font-mono text-[var(--muted)]">FastAPI · pandas · Plotly</span> on AWS ·{' '}
              Clerk for identity · <span className="font-mono text-[var(--muted)]">JSON</span> on disk. No database.
            </p>
          </Reveal>

          <Reveal delay={80} className="mt-12">
            <Grid cols={3} gap="lg">
              {DECISIONS.map((d) => (
                <div key={d.title}>
                  <Row gap="sm" align="center" className="mb-2.5">
                    <span className="shrink-0 grid place-items-center w-8 h-8 rounded-lg border border-[var(--border-2)] bg-[var(--raised)]">
                      <d.icon size={16} strokeWidth={1.5} className="text-[var(--accent)]" />
                    </span>
                    <h3 className="text-[15px] font-semibold text-[var(--text)] m-0">{d.title}</h3>
                  </Row>
                  <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0">{d.body}</p>
                </div>
              ))}
            </Grid>
          </Reveal>

          <Reveal delay={100} className="mt-10">
            <a
              href={`${REPO_URL}/blob/main/ARCHITECTURE.md`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-[13.5px] text-[var(--accent)] hover:underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] rounded"
            >
              Read the full architecture &amp; invariants <ArrowRight size={14} strokeWidth={1.5} />
            </a>
          </Reveal>
        </div>
      </section>

      {/* Pricing, plainly — free, with the real per-run cost named */}
      <section id="pricing" className="border-t border-[var(--border)] py-20">
        <div className={`${SECTION} max-w-[820px]`}>
          <Reveal>
            <h2 className="text-[28px] lg:text-[32px] font-semibold m-0 mb-3 tracking-tight text-balance">Pricing, plainly</h2>
            <p className="text-[14.5px] text-[var(--muted)] leading-relaxed m-0 max-w-[600px]">
              The app is <span className="text-[var(--text)] font-medium">free</span> and open source. You
              bring your own AI key (OpenRouter, and optionally Google Gemini) and pay the provider
              directly for what you run — there’s no markup and no bill from us. Rough real costs, so
              money is never a surprise:
            </p>
          </Reveal>
          <Reveal delay={70} className="mt-8">
            <Grid cols={3} gap="md">
              {[
                { k: 'Build a dashboard', v: '$0', d: 'Charts, metrics and the table are computed deterministically — no AI call at all.' },
                { k: 'Ask a question / edit', v: '~$0.001', d: 'One fast-model call to turn your words into a query spec. Fractions of a cent.' },
                { k: 'A full research run', v: '~2–20¢', d: '3 web searches + a multi-model council. Depends entirely on the models you choose.' },
              ].map((p) => (
                <div key={p.k} className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5">
                  <div className="text-[13px] text-[var(--muted)]">{p.k}</div>
                  <div className="text-[26px] font-semibold text-[var(--text)] tabular-nums mt-1">{p.v}</div>
                  <p className="text-[12.5px] text-[var(--faint)] leading-relaxed mt-2 m-0">{p.d}</p>
                </div>
              ))}
            </Grid>
          </Reveal>
          <Reveal delay={90} className="mt-6">
            <Row gap="sm" align="center" className="text-[13px] text-[var(--muted)]">
              <Check size={15} strokeWidth={2} className="text-[#5ad08a] shrink-0" />
              No card, and no AI key, to start — the <Link href="/demo" className="text-[var(--accent)] hover:underline underline-offset-2">live demo</Link> needs neither.
            </Row>
          </Reveal>
        </div>
      </section>

      {/* FAQ — informative, and emits FAQPage structured data above */}
      <section className="border-t border-[var(--border)] py-20">
        <div className={`${SECTION} max-w-[760px]`}>
          <Reveal>
            <h2 className="text-[28px] font-semibold m-0 mb-8 tracking-tight">Questions, answered</h2>
          </Reveal>
          <Reveal className="flex flex-col divide-y divide-[var(--border)] border-y border-[var(--border)]">
            {FAQ.map((f) => (
              <details key={f.q} className="group py-4">
                <summary className="flex items-center justify-between gap-4 cursor-pointer list-none text-[15px] font-medium text-[var(--text)]">
                  {f.q}
                  <span className="shrink-0 text-[var(--muted)] transition-transform group-open:rotate-45 text-[20px] leading-none">+</span>
                </summary>
                <p className="text-[13.5px] text-[var(--muted)] leading-relaxed mt-3 mb-0 max-w-[640px]">{f.a}</p>
              </details>
            ))}
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--border)] py-24 relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(600px 260px at 50% 100%, oklch(0.28 0.09 250 / 0.30), transparent 70%)' }}
        />
        <Reveal className={`${SECTION} relative text-center`}>
          <h2 className="text-[32px] font-semibold m-0 mb-3 tracking-tight text-balance">Your data has answers. Go get them.</h2>
          <p className="text-[14.5px] text-[var(--muted)] m-0 mb-8">Free to use — sign in and start building living dashboards in minutes.</p>
          <Link
            href="/studio"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[15px] font-medium hover:bg-[var(--new-chat-hover)] transition"
          >
            <MousePointerClick size={17} strokeWidth={1.5} /> Open the studio
          </Link>
        </Reveal>
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
            <Link href="/about" className="hover:text-[var(--text)] transition">About</Link>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-[var(--border-2)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--border-3)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] transition"
            >
              <Star size={13} strokeWidth={1.5} /> Star on GitHub
            </a>
            <span>
              Built by{' '}
              {/* Byline links the author's site, NOT the GitHub profile (the star button is the repo). */}
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
        </div>
      </footer>
    </div>
  );
}
