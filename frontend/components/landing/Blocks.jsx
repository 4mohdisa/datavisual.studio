// Presentational "block" components for the landing page — hand-drawn SVG
// charts in the product palette. Zero chart-library dependencies, so the
// landing paints instantly. Server-component safe (no hooks, no browser APIs).

export const PALETTE = ['#4a90e2', '#9b59e0', '#5cb85c', '#e3c34d', '#e36a6a'];

const CARD = 'rounded-xl border border-[var(--border-2)] bg-[var(--raised)]';

export function MetricBlock({ label, value, delta, down = false }) {
  return (
    <div className={`${CARD} p-4 min-w-[150px]`}>
      <div className="text-[10.5px] uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="text-[22px] font-bold text-[var(--text)] mt-1 tabular-nums">{value}</div>
      {delta && (
        <div className={`inline-block mt-1.5 px-1.5 py-0.5 rounded text-[10.5px] font-medium ${
          down ? 'bg-[oklch(0.2_0.05_25)] text-[#e36a6a]' : 'bg-[oklch(0.2_0.05_150)] text-[#5ad08a]'
        }`}>
          {down ? '▾' : '▴'} {delta}
        </div>
      )}
    </div>
  );
}

export function MiniBars({ title = 'Revenue by region', values = [62, 88, 46, 71], color = PALETTE[2] }) {
  const max = Math.max(...values);
  const w = 26, gap = 12;
  return (
    <div className={`${CARD} p-4`}>
      <div className="text-[11.5px] font-semibold text-[var(--muted)] mb-2">{title}</div>
      <svg viewBox="0 0 160 90" className="w-full" aria-hidden="true">
        {[22, 45, 68].map((y) => (
          <line key={y} x1="0" x2="160" y1={y} y2={y} stroke="oklch(0.22 0 0)" strokeWidth="1" />
        ))}
        {values.map((v, i) => {
          const h = (v / max) * 72;
          return (
            <rect
              key={i}
              x={8 + i * (w + gap)}
              y={86 - h}
              width={w}
              height={h}
              rx="4"
              fill={color}
              opacity={0.55 + 0.45 * (v / max)}
            />
          );
        })}
      </svg>
    </div>
  );
}

export function MiniLine({ title = 'Units over time', series = null }) {
  const lines = series || [
    { color: PALETTE[0], pts: [58, 44, 52, 34, 40, 22, 18] },
    { color: PALETTE[1], pts: [66, 60, 48, 52, 38, 42, 30] },
  ];
  const toPath = (pts) =>
    pts.map((y, i) => `${i === 0 ? 'M' : 'L'} ${8 + i * 24} ${y + 8}`).join(' ');
  return (
    <div className={`${CARD} p-4`}>
      <div className="text-[11.5px] font-semibold text-[var(--muted)] mb-2">{title}</div>
      <svg viewBox="0 0 160 90" className="w-full" aria-hidden="true">
        {[22, 45, 68].map((y) => (
          <line key={y} x1="0" x2="160" y1={y} y2={y} stroke="oklch(0.22 0 0)" strokeWidth="1" />
        ))}
        {lines.map((l, li) => (
          <g key={li}>
            <path d={toPath(l.pts)} fill="none" stroke={l.color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={8 + (l.pts.length - 1) * 24} cy={l.pts[l.pts.length - 1] + 8} r="3.5" fill={l.color} stroke="var(--background)" strokeWidth="1.5" />
          </g>
        ))}
      </svg>
    </div>
  );
}

export function MiniDonut({ title = 'Share by product', segments = [42, 33, 25] }) {
  const total = segments.reduce((a, b) => a + b, 0);
  const C = 2 * Math.PI * 30;
  let acc = 0;
  return (
    <div className={`${CARD} p-4`}>
      <div className="text-[11.5px] font-semibold text-[var(--muted)] mb-2">{title}</div>
      <div className="flex items-center gap-4">
        <svg viewBox="0 0 80 80" className="w-[84px] shrink-0" aria-hidden="true">
          {segments.map((s, i) => {
            const frac = s / total;
            const el = (
              <circle
                key={i}
                cx="40" cy="40" r="30"
                fill="none"
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth="13"
                strokeDasharray={`${frac * C - 2} ${C - frac * C + 2}`}
                strokeDashoffset={-acc * C + C / 4}
              />
            );
            acc += frac;
            return el;
          })}
        </svg>
        <div className="flex flex-col gap-1.5">
          {segments.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
              <span className="w-2 h-2 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
              {Math.round((s / total) * 100)}%
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function InsightBlock({ title = 'Internet research', lines = 3, sources = ['reuters.com', 'oecd.org'] }) {
  const widths = ['92%', '78%', '85%', '64%'];
  return (
    <div className="rounded-xl border border-[#232a3a] bg-[#12161f] p-4">
      <div className="flex items-center gap-1.5 mb-2.5">
        <span className="w-2 h-2 rounded-full bg-[var(--accent)]" />
        <span className="text-[11.5px] font-semibold text-[#9db8e8]">{title}</span>
      </div>
      <div className="flex flex-col gap-1.5 mb-3">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="h-[7px] rounded bg-[oklch(0.24_0.01_250)]" style={{ width: widths[i % widths.length] }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((s) => (
          <span key={s} className="px-2 py-0.5 rounded-full border border-[#2a344a] text-[10px] text-[var(--accent)]">
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

// A composed mock dashboard — the hero visual.
export function DashboardMock() {
  return (
    <div className="rounded-2xl border border-[var(--border-2)] bg-[oklch(0.14_0_0)] p-4 shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
      {/* window chrome */}
      <div className="flex items-center gap-1.5 mb-3">
        {['#e36a6a', '#e3c34d', '#5cb85c'].map((c) => (
          <span key={c} className="w-2.5 h-2.5 rounded-full" style={{ background: c, opacity: 0.75 }} />
        ))}
        <span className="ml-2 text-[11px] text-[var(--faint)]">H2 Sales — Research Board</span>
        <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[var(--muted)]">⟳ Refresh data</span>
      </div>
      <div className="grid grid-cols-3 gap-2.5 mb-2.5">
        <MetricBlock label="Total revenue" value="3.85M" delta="6.9% YoY" />
        <MetricBlock label="Web sources" value="30" delta="1 authoritative" />
        <MetricBlock label="Consensus" value="High" delta="4 models" />
      </div>
      <div className="grid grid-cols-2 gap-2.5 mb-2.5">
        <MiniLine />
        <MiniBars />
      </div>
      <div className="grid grid-cols-2 gap-2.5">
        <MiniDonut />
        <InsightBlock />
      </div>
    </div>
  );
}
