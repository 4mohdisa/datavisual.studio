import Plot from 'react-plotly.js';

// Section 1 — "Mathematical Model Predictions":
//   1a) three model cards (A = ELO Monte Carlo, B = ELO-Poisson/Dixon-Coles,
//       C = XGBoost placeholder), each listing its top-8 raw point estimates,
//   1b) an ensemble horizontal bar chart with per-entity model-agreement dots,
//   1c) a Model A vs B vs Ensemble comparison chart.
// Sections 2 (Combined), 3 (AI Analysis) and 4 (charts) live in their own components.

const MODEL_COLORS = { a: '#4a90e2', b: '#9b59e0', c: '#5cb85c', ensemble: '#ffffff' };
const AGREE_HEX = { green: '#4ade80', amber: '#fbbf24', red: '#f87171' };

function agreementColor(a) {
  if (a >= 0.85) return AGREE_HEX.green;
  if (a >= 0.65) return AGREE_HEX.amber;
  return AGREE_HEX.red;
}

// Raw single-value model output table (point_estimate%, top 8).
function PointTable({ rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <table className="w-full border-collapse text-[12px]">
      <tbody>
        {rows.slice(0, 8).map((p, i) => (
          <tr key={i} className="border-b border-[var(--border)] last:border-0">
            <td className="py-1 pr-2 text-[oklch(0.85_0_0)]">{p.entity}</td>
            <td className="py-1 text-right text-[oklch(0.75_0_0)] tabular-nums">{p.point_estimate}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ModelCard({ title, subheader, rows, placeholder }) {
  return (
    <div className="flex-1 basis-[260px] max-[900px]:basis-full rounded-[0.2rem] border border-[oklch(0.22_0_0)] bg-[oklch(0.15_0_0)] p-4">
      <div className="text-[13px] font-semibold text-white">{title}</div>
      <div className="text-[11px] text-[var(--muted)] mb-2">{subheader}</div>
      {placeholder ? (
        <div className="mt-1 rounded border border-dashed border-[var(--border-2)] p-3 text-center text-[11px] text-[var(--faint)] leading-relaxed">
          {placeholder}
        </div>
      ) : (
        <PointTable rows={rows} />
      )}
    </div>
  );
}

// 1b — ensemble probabilities as a horizontal bar chart; a coloured marker at the
// left of each bar encodes Model A/B agreement (hover for the breakdown).
function EnsembleChart({ ensemble, aMap, bMap, cMap, showAgreement, showModelC }) {
  const rows = (ensemble || []).slice(0, 8);
  if (rows.length === 0) return null;
  // Reverse so the highest-probability entity sits at the top of the y axis.
  const ordered = [...rows].reverse();
  const entities = ordered.map((r) => r.entity);

  const data = [
    {
      type: 'bar',
      orientation: 'h',
      x: ordered.map((r) => r.point_estimate),
      y: entities,
      marker: { color: '#cbd5e1' },
      hovertemplate: '%{y}: %{x}%<extra></extra>',
      showlegend: false,
    },
  ];

  if (showAgreement) {
    data.push({
      type: 'scatter',
      mode: 'markers',
      x: ordered.map(() => 0),
      y: entities,
      marker: { size: 12, color: ordered.map((r) => agreementColor(r.model_agreement ?? 1)) },
      hovertext: ordered.map((r) => {
        const a = aMap[r.entity];
        const b = bMap[r.entity];
        if (showModelC) {
          const c = cMap[r.entity];
          return `Model A: ${a ?? '–'}% · Model B: ${b ?? '–'}% · Model C: ${c ?? '–'}%<br>Average: ${r.point_estimate}%`;
        }
        const diff = a != null && b != null ? Math.abs(a - b).toFixed(1) : '–';
        const agr = Math.round((r.model_agreement ?? 1) * 100);
        return `Model A: ${a ?? '–'}% · Model B: ${b ?? '–'}%<br>Difference: ${diff}% · Agreement: ${agr}%`;
      }),
      hoverinfo: 'text',
      showlegend: false,
    });
  }

  const layout = {
    xaxis: { title: 'Probability %' },
    yaxis: { automargin: true },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: 'rgb(220,220,220)' },
    margin: { l: 90, r: 20, t: 10, b: 40 },
    height: 40 * entities.length + 70,
    autosize: true,
    bargap: 0.35,
  };

  return (
    <Plot
      data={data}
      layout={layout}
      style={{ width: '100%', height: `${40 * entities.length + 70}px` }}
      useResizeHandler={true}
      config={{ displayModeBar: false, responsive: true }}
    />
  );
}

// 1c — where the mathematical approaches diverge. Model C (green) appears as a
// third bar when an XGBoost model was trained from match history.
function ComparisonChart({ modelA, modelB, modelC, ensemble }) {
  const top = (ensemble || []).slice(0, 5).map((r) => r.entity);
  if (top.length === 0) return null;
  const lookup = (rows) => Object.fromEntries((rows || []).map((r) => [r.entity, r.point_estimate]));
  const a = lookup(modelA);
  const b = lookup(modelB);
  const c = lookup(modelC);
  const e = lookup(ensemble);

  const series = [
    { name: 'Model A', color: MODEL_COLORS.a, src: a },
    { name: 'Model B', color: MODEL_COLORS.b, src: b },
    { name: 'Model C', color: MODEL_COLORS.c, src: c },
    { name: 'Ensemble', color: MODEL_COLORS.ensemble, src: e },
  ].map((t) => ({
    type: 'bar',
    name: t.name,
    x: top,
    y: top.map((ent) => t.src[ent] ?? 0),
    marker: { color: t.color },
  }));

  // Drop any model trace with no data (e.g. Model B on softmax datasets, or
  // Model C when no match history was uploaded) so it isn't misleading.
  const data = series.filter((tr) => {
    if (tr.name === 'Model A' || tr.name === 'Ensemble') return true;
    return tr.y.some((v) => v > 0);
  });

  const layout = {
    barmode: 'group',
    title: 'Where models agree and disagree',
    xaxis: { title: '' },
    yaxis: { title: 'Probability %' },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: 'rgb(220,220,220)' },
    margin: { l: 50, r: 20, t: 40, b: 40 },
    height: 300,
    autosize: true,
    legend: { orientation: 'h', y: -0.2 },
  };

  return (
    <Plot
      data={data}
      layout={layout}
      style={{ width: '100%', height: '300px' }}
      useResizeHandler={true}
      config={{ displayModeBar: false, responsive: true }}
    />
  );
}

function AgreementLegend() {
  const item = (hex, label) => (
    <span className="inline-flex items-center gap-1">
      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: hex }} />
      {label}
    </span>
  );
  return (
    <div className="flex items-center gap-4 text-[10px] text-[var(--muted)] mt-1">
      {item(AGREE_HEX.green, 'Models agree (≥85%)')}
      {item(AGREE_HEX.amber, 'Some divergence (≥65%)')}
      {item(AGREE_HEX.red, 'Significant divergence (<65%)')}
    </div>
  );
}

export default function PredictionSuite({ suite, meta = {} }) {
  if (!suite || (!suite.combined?.length && !suite.model_a?.length)) return null;

  const {
    model_a = [], model_b = [], model_c = [], ensemble = [],
  } = suite;

  const sims = (meta.n_simulations || 10000).toLocaleString();
  const rho = typeof meta.rho === 'number' ? meta.rho.toFixed(3) : '-0.107';
  const matchCount = (meta.model_c_match_count || 0).toLocaleString();

  const aMap = Object.fromEntries(model_a.map((r) => [r.entity, r.point_estimate]));
  const bMap = Object.fromEntries(model_b.map((r) => [r.entity, r.point_estimate]));
  const cMap = Object.fromEntries(model_c.map((r) => [r.entity, r.point_estimate]));
  const showModelC = model_c.length > 0;
  const showAgreement = model_b.length > 0;

  return (
    <div className="flex flex-col gap-4">
      {/* 1a — three model cards */}
      <div className="flex flex-wrap gap-3">
        <ModelCard
          title="Model A"
          subheader={`ELO Monte Carlo · ${sims} simulations`}
          rows={model_a}
        />
        <ModelCard
          title="Model B"
          subheader={`ELO-Poisson · Dixon-Coles ρ=${rho}`}
          rows={model_b}
          placeholder={model_b.length === 0 ? 'No scoreline model available for this dataset.' : null}
        />
        <ModelCard
          title="Model C"
          subheader={showModelC ? `XGBoost · Trained on ${matchCount} matches` : 'XGBoost · Match history required'}
          rows={model_c}
          placeholder={
            showModelC
              ? null
              : 'Upload a match history CSV alongside your dataset to enable the XGBoost model. Required columns: date, home_team, away_team, home_goals, away_goals'
          }
        />
      </div>

      {/* 1b — ensemble average */}
      {ensemble.length > 0 && (
        <div className="rounded-[0.2rem] border border-[oklch(0.22_0_0)] bg-[oklch(0.15_0_0)] p-4">
          <div className="text-[13px] font-semibold text-white">Ensemble Average</div>
          <div className="text-[11px] text-[var(--muted)] mb-2">
            Mean of all available mathematical models weighted equally
          </div>
          <EnsembleChart
            ensemble={ensemble}
            aMap={aMap}
            bMap={bMap}
            cMap={cMap}
            showAgreement={showAgreement}
            showModelC={showModelC}
          />
          {showAgreement && <AgreementLegend />}
        </div>
      )}

      {/* 1c — model comparison */}
      <ComparisonChart modelA={model_a} modelB={model_b} modelC={model_c} ensemble={ensemble} />
    </div>
  );
}
