// Looping, on-brand animated demonstrations of the core features. Pure CSS
// (classes defined in globals.css) so these stay server components — no JS
// island, no bundle cost — and settle to a readable end-state under
// prefers-reduced-motion.

const PALETTE = ['#4a90e2', '#9b59e0', '#5cb85c', '#e3c34d', '#e36a6a'];
const PANEL = 'relative rounded-2xl border border-[var(--border-2)] bg-[oklch(0.14_0_0)] p-5 overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.4)]';

// 1 — The living monitor: value, a delta chip that arrives, and a "what
// changed" feed that fills in line by line.
export function LiveMonitorDemo() {
  return (
    <div className={PANEL} aria-hidden="true">
      <div className="text-[11px] uppercase tracking-wide text-[var(--faint)] mb-3">Live monitor · one update</div>
      <div className="flex items-end gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">Total revenue</div>
          <div className="text-[30px] font-bold text-[var(--text)] tabular-nums leading-none mt-1">$3.85M</div>
        </div>
        <span className="dv-cycle inline-flex items-center px-2 py-0.5 rounded-md text-[12px] font-medium bg-[oklch(0.22_0.06_150)] text-[#5ad08a] mb-1" style={{ animationDelay: '0.3s' }}>
          ▲ 12.4%
        </span>
      </div>
      <div className="mt-4 pt-3 border-t border-[var(--border)]">
        <div className="text-[11px] font-semibold text-[var(--muted)] mb-2">What changed</div>
        <div className="flex flex-col gap-1.5">
          <div className="dv-cycle flex items-center gap-2 text-[12.5px] text-[var(--muted)]" style={{ animationDelay: '0.7s' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: PALETTE[0] }} /> Revenue 3.43M → <span className="text-[var(--text)]">3.85M</span>
          </div>
          <div className="dv-cycle flex items-center gap-2 text-[12.5px] text-[var(--muted)]" style={{ animationDelay: '1.15s' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: PALETTE[2] }} /> 3 new sources on <span className="text-[var(--text)]">“pricing pressure”</span>
          </div>
          <div className="dv-cycle flex items-center gap-2 text-[12.5px] text-[var(--muted)]" style={{ animationDelay: '1.6s' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: PALETTE[3] }} /> Consensus shifted <span className="text-[var(--text)]">medium → high</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// 2 — Instant dashboard: metric chips, then bars grow, then a line draws.
export function BuildDemo() {
  const bars = [46, 72, 58, 88, 66, 94];
  return (
    <div className={PANEL} aria-hidden="true">
      <div className="grid grid-cols-3 gap-2 mb-4">
        {['Revenue', 'Units', 'Regions'].map((l, i) => (
          <div key={l} className="dv-cycle rounded-lg border border-[var(--border-2)] bg-[var(--raised)] px-3 py-2" style={{ animationDelay: `${0.15 * i}s` }}>
            <div className="text-[9px] uppercase tracking-wide text-[var(--faint)]">{l}</div>
            <div className="text-[15px] font-bold text-[var(--text)] tabular-nums">{['3.85M', '49k', '4'][i]}</div>
          </div>
        ))}
      </div>
      <svg viewBox="0 0 240 108" className="w-full" aria-hidden="true">
        {[30, 60, 90].map((y) => <line key={y} x1="0" x2="240" y1={y} y2={y} stroke="oklch(0.22 0 0)" strokeWidth="1" />)}
        {bars.map((v, i) => {
          const h = (v / 100) * 96;
          return (
            <rect key={i} className="dv-bar" style={{ animationDelay: `${0.5 + i * 0.09}s` }}
              x={12 + i * 38} y={104 - h} width="22" height={h} rx="4"
              fill={PALETTE[i % PALETTE.length]} opacity="0.9" />
          );
        })}
        <path className="dv-draw" style={{ '--dash': 320, animationDelay: '0.9s' }}
          d="M 20 78 L 58 60 L 96 66 L 134 40 L 172 48 L 210 22"
          fill="none" stroke="#e8e8ea" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// 3 — Edit by chat: a prompt types out, a pie sweeps in.
export function ChatEditDemo() {
  const C = 2 * Math.PI * 26;
  const segs = [42, 33, 25];
  let acc = 0;
  return (
    <div className={PANEL} aria-hidden="true">
      <div className="flex items-center gap-2 bg-[var(--surface-input)] border border-[var(--border-2)] rounded-xl px-3 py-2.5">
        <span className="text-[var(--accent)] text-[13px]">›</span>
        <span className="dv-type text-[13px] text-[var(--text)] whitespace-nowrap">add a pie of revenue by product</span>
        <span className="ml-auto w-6 h-6 rounded-full bg-white text-black flex items-center justify-center text-[12px]">↑</span>
      </div>
      <div className="dv-cycle mt-4 flex items-center gap-4" style={{ animationDelay: '2s' }}>
        <svg viewBox="0 0 72 72" className="w-[80px] shrink-0" aria-hidden="true">
          {segs.map((s, i) => {
            const frac = s / 100;
            const el = (
              <circle key={i}
                cx="36" cy="36" r="26" fill="none" stroke={PALETTE[i % PALETTE.length]} strokeWidth="11"
                strokeDasharray={`${frac * C} ${C}`} strokeDashoffset={-acc * C} transform="rotate(-90 36 36)" />
            );
            acc += frac;
            return el;
          })}
        </svg>
        <div className="flex flex-col gap-1.5">
          {['Product A · 42%', 'Product B · 33%', 'Product C · 25%'].map((t, i) => (
            <div key={t} className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
              <span className="w-2 h-2 rounded-full" style={{ background: PALETTE[i] }} /> {t}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// 4 — The AI council: models answer, review, a chairman synthesises a report.
export function CouncilDemo() {
  return (
    <div className={PANEL} aria-hidden="true">
      <div className="flex items-center justify-between gap-2 mb-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="dv-cycle dv-pulse flex-1 rounded-lg border border-[var(--border-2)] bg-[var(--raised)] px-2 py-2 text-center" style={{ animationDelay: `${i * 0.25}s` }}>
            <div className="w-2 h-2 rounded-full mx-auto mb-1" style={{ background: PALETTE[i] }} />
            <div className="text-[10px] text-[var(--muted)]">Model {String.fromCharCode(65 + i)}</div>
          </div>
        ))}
      </div>
      <div className="flex justify-center mb-3">
        <div className="dv-cycle text-[var(--faint)] text-[15px]" style={{ animationDelay: '1.1s' }}>↓ anonymous peer review ↓</div>
      </div>
      <div className="dv-cycle rounded-lg border border-[var(--accent)] bg-[oklch(0.16_0.03_250)] px-3 py-2.5 flex items-center gap-2" style={{ animationDelay: '1.5s' }}>
        <span className="w-6 h-6 rounded-md bg-[var(--accent)] text-white flex items-center justify-center text-[12px] shrink-0">✓</span>
        <div>
          <div className="text-[12.5px] font-semibold text-[var(--text)]">Chairman synthesis</div>
          <div className="text-[10.5px] text-[var(--muted)]">one cited answer · consensus: high</div>
        </div>
      </div>
    </div>
  );
}
