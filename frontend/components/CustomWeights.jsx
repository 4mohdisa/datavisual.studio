import { useState } from 'react';
import { Settings2 } from 'lucide-react';
import { DEFAULT_WEIGHTS as DEFAULTS } from '../lib/constants';

// 6.2 — adjust the dataset/internet/council weights and recombine the stored
// per-source probabilities client-side (no new API calls).

function recombine(rows, w) {
  // w in 0-100; convert to 0-1. Per entity, weighted average of the sources that
  // have data (weights renormalised to present), then normalise across entities.
  const wd = { dataset: w.dataset / 100, internet: w.internet / 100, council: w.council / 100 };
  const raw = rows.map((r) => {
    const present = [];
    if (r.ensemble_pct != null) present.push(['dataset', r.ensemble_pct / 100]);
    if (r.internet_pct != null) present.push(['internet', r.internet_pct / 100]);
    if (r.council_pct != null) present.push(['council', r.council_pct / 100]);
    if (present.length === 0) return { entity: r.entity, val: 0 };
    const tw = present.reduce((s, [k]) => s + wd[k], 0) || 1;
    const val = present.reduce((s, [k, v]) => s + (v * wd[k]) / tw, 0);
    return { entity: r.entity, val };
  });
  const total = raw.reduce((s, x) => s + x.val, 0) || 1;
  return raw
    .map((x) => ({ entity: x.entity, pct: +((x.val / total) * 100).toFixed(1) }))
    .sort((a, b) => b.pct - a.pct);
}

function Slider({ label, value, onChange }) {
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <span className="w-16 text-[var(--muted)]">{label}</span>
      <input type="range" min="0" max="100" value={value} onChange={(e) => onChange(Number(e.target.value))} className="flex-1 accent-[var(--accent)]" />
      <span className="w-9 text-right tabular-nums text-[var(--text)]">{value}%</span>
    </div>
  );
}

export default function CustomWeights({ suite }) {
  const rows = suite?.source_breakdown || [];
  const [open, setOpen] = useState(false);
  const [weights, setWeights] = useState(DEFAULTS);
  const [result, setResult] = useState(null);

  if (rows.length === 0) return null;

  // Adjust one weight; rebalance the other two proportionally so the sum stays 100.
  const setWeight = (key, val) => {
    const others = Object.keys(weights).filter((k) => k !== key);
    const remaining = 100 - val;
    const othersTotal = others.reduce((s, k) => s + weights[k], 0) || 1;
    const next = { [key]: val };
    others.forEach((k) => { next[k] = Math.round((weights[k] / othersTotal) * remaining); });
    // Fix rounding drift onto the last slider.
    const drift = 100 - Object.values(next).reduce((s, v) => s + v, 0);
    next[others[others.length - 1]] += drift;
    setWeights(next);
  };

  return (
    <div className="mt-3">
      <button onClick={() => setOpen((o) => !o)} className="inline-flex items-center gap-1.5 text-[12px] text-[var(--muted)] hover:text-[var(--text)] transition">
        <Settings2 size={14} strokeWidth={1.5} /> Adjust weights
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-3 flex flex-col gap-2 max-w-[420px]">
          <Slider label="Dataset" value={weights.dataset} onChange={(v) => setWeight('dataset', v)} />
          <Slider label="Internet" value={weights.internet} onChange={(v) => setWeight('internet', v)} />
          <Slider label="Council" value={weights.council} onChange={(v) => setWeight('council', v)} />
          <div className="flex gap-2 mt-1">
            <button onClick={() => setResult(recombine(rows, weights))} className="px-3 py-1 rounded-md bg-[var(--accent)] text-white text-[12px]">Recalculate</button>
            <button onClick={() => { setWeights(DEFAULTS); setResult(null); }} className="px-3 py-1 rounded-md border border-[var(--border-2)] text-[12px] text-[var(--muted)] hover:text-[var(--text)]">Reset to defaults</button>
          </div>
          {result && (
            <table className="w-full border-collapse text-[12px] mt-1">
              <tbody>
                {result.slice(0, 10).map((r, i) => (
                  <tr key={i} className="border-b border-[var(--border)] last:border-0">
                    <td className="py-1 text-[oklch(0.85_0_0)]">{r.entity}</td>
                    <td className="py-1 text-right tabular-nums text-[var(--text)]">
                      {Math.max(0.1, r.pct - 1.5).toFixed(1)}–{Math.min(99.9, r.pct + 1.5).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
