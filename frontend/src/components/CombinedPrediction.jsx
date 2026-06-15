// Section 2 — the weighted combination of all sources into the final range.
// Renders nothing when there's no per-entity breakdown (e.g. text-only mode).
const HEADERS = ['Entity', 'Math models', 'Internet', 'Council', 'Final range'];

function Cell({ value }) {
  // Distinct muted colour for missing data so it reads clearly as "no data" (1.7).
  if (value == null) return <span className="text-[oklch(0.35_0_0)]">—</span>;
  return <span className="tabular-nums">{value}%</span>;
}

export default function CombinedPrediction({ suite, meta = {} }) {
  const rows = suite?.source_breakdown || [];
  if (rows.length === 0) return null;
  const host = meta.host_entity || null;

  return (
    <div className="flex flex-col gap-2">
      <div className="text-[12px] text-[var(--muted)]">
        Dataset ensemble 40% · Internet research 35% · AI council 25%
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px] border border-[var(--border-2)]">
          <thead>
            <tr>
              {HEADERS.map((h) => (
                <th key={h} className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-left border border-[var(--border-2)]">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="odd:bg-[var(--raised)]">
                <td className="px-3 py-2 border border-[var(--border)] text-[oklch(0.88_0_0)]">
                  {r.entity}
                  {host && r.entity === host && <span title="Host nation (+65 ELO)"> 🏠</span>}
                </td>
                <td className="px-3 py-2 border border-[var(--border)] text-[oklch(0.82_0_0)]"><Cell value={r.ensemble_pct} /></td>
                <td className="px-3 py-2 border border-[var(--border)] text-[oklch(0.82_0_0)]"><Cell value={r.internet_pct} /></td>
                <td className="px-3 py-2 border border-[var(--border)] text-[oklch(0.82_0_0)]"><Cell value={r.council_pct} /></td>
                <td className="px-3 py-2 border border-[var(--border)] text-white font-semibold tabular-nums">
                  {r.low_pct}–{r.high_pct}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[11px] italic text-[var(--muted)] leading-relaxed">
        Dataset ensemble (40%) + Internet consensus (35%) + AI council agreement (25%) = Final prediction.
        Sources with no data for an entity are excluded and remaining weights are rescaled.
        {host && <> · 🏠 Host advantage applied (+{meta.host_boost || 65} ELO)</>}
      </div>
    </div>
  );
}
