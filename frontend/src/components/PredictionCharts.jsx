import Plot from 'react-plotly.js';

// Section 4 — "How we got here". Renders the explanation charts in a fixed order:
//   A weight breakdown (donut) · B source comparison (grouped bar)
//   C ELO trajectory (line)    · D confidence breakdown (table)
// (the confidence_ranges chart is intentionally omitted from this section).
const ORDER = ['weight_breakdown', 'source_comparison', 'elo_trajectory', 'breakdown_table'];

function PChart({ chart }) {
  if (!chart || !chart.plotly_json) return null;
  const spec = chart.plotly_json;
  const height = chart.height || 300;
  const layout = {
    ...(spec.layout || {}),
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: 'rgb(220,220,220)' },
    margin: { l: 50, r: 20, t: 40, b: 40 },
    height,
    autosize: true,
    width: undefined,
  };
  return (
    <div>
      <Plot
        data={spec.data || []}
        layout={layout}
        style={{ width: '100%', height: `${height}px` }}
        useResizeHandler={true}
        config={{ displayModeBar: false, responsive: true }}
      />
      {chart.note && <div className="text-[12px] text-[var(--faint)] mt-1">{chart.note}</div>}
    </div>
  );
}

export default function PredictionCharts({ charts }) {
  if (!charts || charts.length === 0) return null;
  const byId = {};
  for (const c of charts) byId[c.id] = c;
  const ordered = ORDER.map((id) => byId[id]).filter(Boolean);
  if (ordered.length === 0) return null;

  return (
    <div className="flex flex-col gap-6">
      {ordered.map((c) => <PChart key={c.id} chart={c} />)}
    </div>
  );
}
