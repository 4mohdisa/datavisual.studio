import ReactMarkdown from 'react-markdown';
import Plot from './LazyPlot';
import PredictionSuite from './PredictionSuite';

// Renders a single prediction-explanation chart (Plotly spec from the backend),
// with the dark/transparent theme the rest of the app uses and an optional note.
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

// The "How this prediction was calculated" explainer box, populated from live
// pipeline counts (n web sources, n council models, simulation count, date).
function ExplainerBox({ meta }) {
  const nSources = meta?.n_sources ?? 0;
  const nCouncil = meta?.n_council ?? 0;
  const today = meta?.today_date || '';
  const sims = (meta?.n_simulations || 10000).toLocaleString();
  return (
    <div className="rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-4 text-[13px] leading-relaxed text-[oklch(0.80_0_0)]">
      <div className="font-semibold text-[var(--text)] mb-2">How this prediction was calculated</div>
      <p>
        <strong>Dataset (40%):</strong> Monte Carlo simulation of {sims} tournament runs using ELO
        ratings from your uploaded data.
      </p>
      <p className="mt-2">
        <strong>Internet (35%):</strong> Probability estimates extracted from {nSources} web
        source{nSources === 1 ? '' : 's'}{today ? ` searched on ${today}` : ''}.
      </p>
      <p className="mt-2">
        <strong>Council (25%):</strong> Agreement extracted from {nCouncil} AI model
        response{nCouncil === 1 ? '' : 's'}, weighted by peer review ranking.
      </p>
    </div>
  );
}

const CONFIDENCE_LABELS = { high: 'High', medium: 'Medium', low: 'Low' };
const CONFIDENCE_CLASS = {
  high: 'bg-[rgba(40,167,69,0.2)] text-[#5cb85c] border border-[rgba(40,167,69,0.4)]',
  medium: 'bg-[rgba(255,193,7,0.15)] text-[#f0ad4e] border border-[rgba(255,193,7,0.3)]',
  low: 'bg-[rgba(220,53,69,0.15)] text-[#d9534f] border border-[rgba(220,53,69,0.3)]',
};

// Confidence dot: high → green, medium → amber, low → muted.
const DOT_CLASS = { high: 'bg-green-400', medium: 'bg-amber-400', low: 'bg-neutral-500' };

// Source pill badges. Keys match PredictionResult.sources_used ("dataset"/"internet"/"council").
const SOURCE_PILLS = {
  dataset: { label: 'Data', className: 'bg-[rgba(74,144,226,0.18)] text-[#6ea8e6] border border-[rgba(74,144,226,0.35)]' },
  internet: { label: 'Web', className: 'bg-[rgba(155,89,224,0.18)] text-[#b08ae6] border border-[rgba(155,89,224,0.35)]' },
  council: { label: 'Council', className: 'bg-[rgba(40,167,69,0.18)] text-[#5cb85c] border border-[rgba(40,167,69,0.35)]' },
};

function SourcePills({ sources }) {
  if (!sources || sources.length === 0) return <span className="text-[var(--faint)]">—</span>;
  return (
    <span className="inline-flex gap-1 flex-wrap">
      {sources.map((s) => {
        const pill = SOURCE_PILLS[s];
        if (!pill) return null;
        return (
          <span key={s} className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${pill.className}`}>
            {pill.label}
          </span>
        );
      })}
    </span>
  );
}

function PredictionTable({ predictions }) {
  if (!predictions || predictions.length === 0) return null;
  // The deterministic engine attaches sources_used; only show the Sources column
  // when at least one row carries it (LLM-fallback predictions don't).
  const hasSources = predictions.some((p) => Array.isArray(p.sources_used) && p.sources_used.length > 0);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px] border border-[var(--border-2)]">
          <thead>
            <tr>
              <th className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-left border border-[var(--border-2)]">Team / Entity</th>
              <th className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-center border border-[var(--border-2)]">Probability</th>
              <th className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-left border border-[var(--border-2)]">Confidence</th>
              {hasSources && (
                <th className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-left border border-[var(--border-2)]">Sources</th>
              )}
            </tr>
          </thead>
          <tbody>
            {predictions.map((p, i) => {
              const conf = ['high', 'medium', 'low'].includes(p.confidence) ? p.confidence : 'medium';
              return (
                <tr key={i} className="odd:bg-[var(--raised)]">
                  <td className="px-3 py-2 border border-[var(--border)] text-[oklch(0.88_0_0)]">{p.entity}</td>
                  <td className="px-3 py-2 border border-[var(--border)] text-center text-[oklch(0.88_0_0)]">
                    {p.low_pct}–{p.high_pct}%
                  </td>
                  <td className="px-3 py-2 border border-[var(--border)] text-[oklch(0.85_0_0)]">
                    <span className={`inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle ${DOT_CLASS[conf]}`} />
                    {conf.charAt(0).toUpperCase() + conf.slice(1)}
                  </td>
                  {hasSources && (
                    <td className="px-3 py-2 border border-[var(--border)]">
                      <SourcePills sources={p.sources_used} />
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {hasSources && (
        <div className="text-[12px] text-[var(--faint)]">
          Probabilities computed by weighted algorithm: dataset 40% · internet research 35% · council consensus 25%
        </div>
      )}
    </div>
  );
}

export default function ChairmanSynthesis({ chairmanSynthesis }) {
  if (!chairmanSynthesis) return null;

  const {
    content, confidence, caveats = [], sources = [], model,
    prediction_table = [], prediction_charts = [], prediction_meta = {},
    prediction_suite = {},
  } = chairmanSynthesis;

  // Index charts by id so we can place each one exactly where the layout wants it.
  const byId = {};
  for (const c of prediction_charts) byId[c.id] = c;
  const hasSuite = (prediction_suite.combined?.length || prediction_suite.model_a?.length);
  const hasExplainerCharts = byId.weight_breakdown || byId.source_comparison
    || byId.confidence_ranges || byId.elo_trajectory || byId.breakdown_table;
  const hasPrediction = hasSuite || prediction_table.length > 0 || prediction_charts.length > 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2.5 flex-wrap">
        {model && <span className="text-xs text-[var(--muted)] italic">{model.split('/').pop()}</span>}
        {confidence && (
          <span className={`inline-block px-2.5 py-0.5 rounded-xl text-[11px] font-bold uppercase tracking-wide ${CONFIDENCE_CLASS[confidence] || ''}`}>
            {CONFIDENCE_LABELS[confidence] || confidence} confidence
          </span>
        )}
      </div>

      {/* Prediction — numbers and charts come FIRST, before the chairman's prose,
          since they are algorithmic and independent of what the chairman writes. */}
      {hasPrediction && (
        <div className="flex flex-col gap-5">
          {/* Sections A (math models + ensemble + comparison) and B (combined). */}
          {hasSuite ? (
            <PredictionSuite suite={prediction_suite} />
          ) : (
            /* Fallback (text mode / LLM-extracted): the simple combined table. */
            prediction_table.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <h3 className="text-lg font-semibold text-white m-0">Prediction</h3>
                <PredictionTable predictions={prediction_table} />
              </div>
            )
          )}

          {/* "How we got here" — the algorithmic explanation charts + weighting box. */}
          {hasExplainerCharts && (
            <div className="flex flex-col gap-4">
              <h4 className="text-sm font-semibold text-[var(--muted)] m-0">How we got here</h4>
              {byId.weight_breakdown && <PChart chart={byId.weight_breakdown} />}
              {byId.source_comparison && <PChart chart={byId.source_comparison} />}
              {byId.confidence_ranges && <PChart chart={byId.confidence_ranges} />}
              {byId.elo_trajectory && <PChart chart={byId.elo_trajectory} />}
              {byId.breakdown_table && <PChart chart={byId.breakdown_table} />}
            </div>
          )}
          <ExplainerBox meta={prediction_meta} />
        </div>
      )}

      {/* Section C — the chairman's prose is explanation, not the prediction itself. */}
      {content && (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-lg font-semibold text-white m-0">AI Analysis</h3>
          <div className="markdown-content text-[oklch(0.85_0_0)] leading-[1.75]">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        </div>
      )}

      {caveats.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-1.5">Caveats</div>
          <ul className="m-0 pl-[18px] text-[oklch(0.78_0_0)] text-[13px] list-disc">
            {caveats.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}

      {sources.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-1.5">Sources referenced</div>
          <ul className="m-0 pl-[18px] text-[oklch(0.78_0_0)] text-[13px] list-disc">
            {sources.map((s, i) => (
              <li key={i}>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] no-underline hover:underline">
                    {s.title || s.url}
                  </a>
                ) : (
                  <span>{s.title}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
