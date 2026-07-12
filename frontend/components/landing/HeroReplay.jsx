'use client';

import { useEffect, useRef, useState } from 'react';

// The hero visual: a dashboard that CHANGES WHILE YOU WATCH — a deterministic,
// scripted replay loop (no backend). A metric counts up, a delta badge flips
// in, and a "what changed" line writes itself. This IS the one true claim of
// the product: it tells you what changed. Honours prefers-reduced-motion by
// rendering the settled end-state. Two accents, and they only appear on a
// delta: green = up/new, amber = changed/stale.

const FROM = 3.43, TO = 3.85;                 // $M
const CHANGED = [
  { c: '#5ad08a', t: 'Revenue', d: '3.43M → 3.85M', badge: '▲ 12.4%' },
  { c: '#5ad08a', t: '3 new sources', d: 'on “pricing pressure”' },
  { c: '#e3c34d', t: 'Consensus', d: 'medium → high' },
];

export default function HeroReplay() {
  const [phase, setPhase] = useState(0);       // 0 idle · 1 tick · 2..4 feed lines
  const [val, setVal] = useState(FROM);
  const reduced = useRef(false);

  useEffect(() => {
    reduced.current = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduced.current) { setPhase(4); setVal(TO); return; }
    let t;
    const cycle = () => {
      const seq = [0, 1, 2, 3, 4];
      let i = 0;
      const step = () => {
        setPhase(seq[i]);
        if (seq[i] === 1) countUp();
        if (seq[i] === 0) setVal(FROM);
        i = (i + 1) % seq.length;
        t = setTimeout(step, i === 1 ? 1200 : 1400);
      };
      step();
    };
    const countUp = () => {
      const start = performance.now();
      const tick = (now) => {
        const k = Math.min(1, (now - start) / 800);
        const eased = 1 - Math.pow(1 - k, 3);
        setVal(FROM + (TO - FROM) * eased);
        if (k < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    cycle();
    return () => clearTimeout(t);
  }, []);

  const showDelta = phase >= 1;
  return (
    <div className="rounded-2xl border border-[var(--border-2)] bg-[oklch(0.14_0_0)] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.55)] select-none">
      <div className="flex items-center gap-1.5 mb-4">
        {['#e36a6a', '#e3c34d', '#5cb85c'].map((c) => <span key={c} className="w-2.5 h-2.5 rounded-full" style={{ background: c, opacity: 0.75 }} />)}
        <span className="ml-2 text-[11px] text-[var(--faint)]">Revenue board · live</span>
        <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full border border-[var(--border-2)] text-[var(--muted)]">updated just now</span>
      </div>

      <div className="flex items-end gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">Total revenue</div>
          <div className="text-[40px] leading-none font-bold text-[var(--text)] mt-1 tabular-nums" style={{ fontVariantNumeric: 'tabular-nums' }}>
            ${val.toFixed(2)}M
          </div>
        </div>
        <span
          key={showDelta ? 'on' : 'off'}
          className={`mb-1.5 inline-flex items-center px-2 py-0.5 rounded-md text-[12.5px] font-medium tabular-nums transition-all duration-300 ${
            showDelta ? 'opacity-100 translate-y-0 bg-[oklch(0.22_0.06_150)] text-[#5ad08a]' : 'opacity-0 translate-y-1'
          }`}
        >
          ▲ 12.4%
        </span>
      </div>

      <div className="mt-5 pt-4 border-t border-[var(--border)]">
        <div className="text-[11px] font-semibold text-[var(--muted)] mb-2.5">What changed</div>
        <div className="flex flex-col gap-2 min-h-[84px]">
          {CHANGED.map((row, i) => {
            const shown = phase >= i + 2 || (reduced.current);
            return (
              <div key={row.t} className={`flex items-center gap-2 text-[13px] transition-all duration-400 ${shown ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1'}`}>
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: row.c }} />
                <span className="text-[var(--muted)]">{row.t}</span>
                <span className="text-[var(--text)] tabular-nums">{row.d}</span>
                {row.badge && <span className="ml-auto text-[11px] tabular-nums" style={{ color: row.c }}>{row.badge}</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
