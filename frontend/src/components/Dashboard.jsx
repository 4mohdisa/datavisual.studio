import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Plot from './LazyPlot';
import { ArrowLeft, Download, Loader2 } from 'lucide-react';
import { api } from '../api';

// ---------------------------------------------------------------------------
// 4.3 — Top metrics strip
// ---------------------------------------------------------------------------
function MetricCard({ label, value, sub }) {
  return (
    <div className="flex-1 min-w-[160px] rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-4">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="text-[24px] font-bold text-[var(--text)] mt-1 tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-[var(--faint)] mt-0.5">{sub}</div>}
    </div>
  );
}

function buildMetrics(summary) {
  const stats = summary?.statistics || {};
  const names = Object.keys(stats);
  if (names.length === 0) return [];
  // Prefer an ELO/rating-like column as the primary metric.
  const primary = names.find((n) => /elo|rating|strength|points|score/i.test(n)) || names[0];
  const winsCol = names.find((n) => /^wins$/i.test(n));
  const p = stats[primary] || {};
  const cards = [
    { label: `Highest ${primary}`, value: p.max?.toLocaleString?.() ?? p.max ?? '–' },
    { label: `Lowest ${primary}`, value: p.min?.toLocaleString?.() ?? p.min ?? '–' },
  ];
  if (winsCol) {
    cards.push({ label: 'Most wins', value: stats[winsCol]?.max?.toLocaleString?.() ?? stats[winsCol]?.max ?? '–' });
    cards.push({ label: `${primary} range`, value: (p.max != null && p.min != null) ? (p.max - p.min).toLocaleString() : '–' });
  } else {
    cards.push({ label: `Mean ${primary}`, value: p.mean?.toLocaleString?.() ?? p.mean ?? '–' });
    cards.push({ label: 'Unique entities', value: (p.unique_count ?? summary?.row_count ?? '–').toLocaleString?.() ?? '–' });
  }
  return cards.slice(0, 4);
}

// ---------------------------------------------------------------------------
// 4.4 — Chart area (grid + tab pills)
// ---------------------------------------------------------------------------
function ChartArea({ charts, onGenerate, generating, canGenerate }) {
  const [tab, setTab] = useState('all');
  if (!charts || charts.length === 0) {
    return <div className="text-[var(--muted)] text-sm">No charts available.</div>;
  }
  const render = (chart, i) => {
    const spec = chart.plotly_json || {};
    return (
      <div key={i} className="rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-3">
        <div className="text-[13px] font-semibold text-[var(--muted)] mb-1 capitalize">{chart.title}</div>
        <Plot
          data={spec.data || []}
          layout={{ ...(spec.layout || {}), paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: 'rgb(220,220,220)' }, margin: { l: 50, r: 20, t: 30, b: 40 }, height: 320, autosize: true, width: undefined }}
          style={{ width: '100%', height: '320px' }}
          useResizeHandler
          config={{ displayModeBar: false, responsive: true }}
        />
      </div>
    );
  };
  const shown = tab === 'all' ? charts : charts.filter((_, i) => String(i) === tab);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {[['all', 'All'], ...charts.map((c, i) => [String(i), c.title])].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-2.5 py-1 rounded-full text-xs transition capitalize ${tab === id ? 'bg-[var(--user-bubble)] text-[var(--text)]' : 'text-[var(--muted)] hover:text-[var(--text)]'}`}
          >
            {label}
          </button>
        ))}
        {onGenerate && canGenerate && (
          <button
            onClick={onGenerate}
            disabled={generating}
            className="ml-auto px-2.5 py-1 rounded-full text-xs border border-[var(--border-2)] text-[var(--muted)] hover:text-[var(--text)] transition disabled:opacity-50"
          >
            {generating ? 'Generating…' : '+ Generate more charts'}
          </button>
        )}
      </div>
      <div className={tab === 'all' ? 'grid grid-cols-1 xl:grid-cols-2 gap-3' : ''}>
        {shown.map(render)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4.5 — Entity comparison (radar + stat cards)
// ---------------------------------------------------------------------------
function EntityComparison({ columns, rows }) {
  const catCol = useMemo(() => columns.find((c) => rows.some((r) => typeof r[c] === 'string')) || columns[0], [columns, rows]);
  const numCols = useMemo(
    () => columns.filter((c) => rows.some((r) => typeof r[c] === 'number')).slice(0, 6),
    [columns, rows],
  );
  // One row per entity (last occurrence wins — latest snapshot).
  const byEntity = useMemo(() => {
    const m = {};
    for (const r of rows) m[r[catCol]] = r;
    return m;
  }, [rows, catCol]);
  const entityNames = useMemo(() => Object.keys(byEntity), [byEntity]);
  const [selected, setSelected] = useState([]);

  useEffect(() => {
    if (entityNames.length && selected.length === 0) setSelected(entityNames.slice(0, 3));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityNames]);

  if (!catCol || numCols.length < 2 || entityNames.length < 2) return null;

  // Normalise each dimension 0-1 across all entities for the radar.
  const ranges = {};
  for (const c of numCols) {
    const vals = entityNames.map((e) => byEntity[e][c]).filter((v) => typeof v === 'number');
    ranges[c] = [Math.min(...vals), Math.max(...vals)];
  }
  const norm = (c, v) => {
    const [lo, hi] = ranges[c];
    return hi === lo ? 0.5 : (v - lo) / (hi - lo);
  };

  const data = selected.map((e) => ({
    type: 'scatterpolar',
    r: [...numCols.map((c) => norm(c, byEntity[e][c] ?? 0)), norm(numCols[0], byEntity[e][numCols[0]] ?? 0)],
    theta: [...numCols, numCols[0]],
    fill: 'toself',
    name: e,
  }));

  const toggle = (e) => setSelected((s) => (s.includes(e) ? s.filter((x) => x !== e) : s.length < 6 ? [...s, e] : s));

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[16px] font-semibold text-[var(--text)]">Entity comparison</div>
      <div className="flex flex-wrap gap-1.5 max-h-[80px] overflow-y-auto">
        {entityNames.slice(0, 48).map((e) => (
          <button
            key={e}
            onClick={() => toggle(e)}
            className={`px-2 py-0.5 rounded-full text-[11px] border transition ${selected.includes(e) ? 'bg-[var(--accent)] text-white border-[var(--accent)]' : 'border-[var(--border-2)] text-[var(--muted)] hover:text-[var(--text)]'}`}
          >
            {e}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Plot
          data={data}
          layout={{ polar: { radialaxis: { visible: true, range: [0, 1], showticklabels: false }, bgcolor: 'rgba(0,0,0,0)' }, paper_bgcolor: 'rgba(0,0,0,0)', font: { color: 'rgb(220,220,220)' }, margin: { l: 40, r: 40, t: 20, b: 20 }, height: 340, showlegend: true, legend: { orientation: 'h', y: -0.1 } }}
          style={{ width: '100%', height: '340px' }}
          useResizeHandler
          config={{ displayModeBar: false, responsive: true }}
        />
        <div className="flex flex-col gap-2">
          {selected.map((e) => (
            <div key={e} className="rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-3">
              <div className="text-[13px] font-semibold text-[var(--text)] mb-1">{e}</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[12px]">
                {numCols.map((c) => (
                  <div key={c} className="flex justify-between gap-2">
                    <span className="text-[var(--muted)] truncate">{c}</span>
                    <span className="text-[var(--text)] tabular-nums">{byEntity[e][c] ?? '–'}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4.6 — Data table (sortable, searchable, paginated, CSV download)
// ---------------------------------------------------------------------------
const PAGE_SIZE = 25;

function DataTable({ columns, rows }) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState({ col: null, dir: 1 });
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = q ? rows.filter((r) => columns.some((c) => String(r[c] ?? '').toLowerCase().includes(q))) : rows;
    if (sort.col) {
      out = [...out].sort((a, b) => {
        const av = a[sort.col], bv = b[sort.col];
        if (av == null) return 1;
        if (bv == null) return -1;
        if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sort.dir;
        return String(av).localeCompare(String(bv)) * sort.dir;
      });
    }
    return out;
  }, [rows, columns, query, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  // Clamp the page during render rather than resetting state in an effect.
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const onSearch = (v) => { setQuery(v); setPage(0); };
  const toggleSort = (c) => { setSort((s) => (s.col === c ? { col: c, dir: -s.dir } : { col: c, dir: 1 })); setPage(0); };

  const downloadCsv = () => {
    const esc = (v) => {
      const s = String(v ?? '');
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [columns.map(esc).join(','), ...filtered.map((r) => columns.map((c) => esc(r[c])).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'dataset.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="text-[16px] font-semibold text-[var(--text)] mr-auto">Data table</div>
        <input
          value={query}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search rows"
          className="bg-[var(--surface-input)] border border-[var(--border-2)] rounded-md px-2.5 py-1.5 text-[13px] text-[var(--text)] placeholder:text-[var(--faint)] outline-none focus:border-[var(--accent)]"
        />
        <button onClick={downloadCsv} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border-2)] text-[13px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--user-bubble)] transition">
          <Download size={14} strokeWidth={1.5} /> CSV
        </button>
      </div>
      <div className="overflow-x-auto border border-[var(--border-2)] rounded-md">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  onClick={() => toggleSort(c)}
                  className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-left cursor-pointer select-none whitespace-nowrap hover:text-white"
                >
                  {c}{sort.col === c ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r, i) => (
              <tr key={i} className="odd:bg-[var(--raised)]">
                {columns.map((c) => (
                  <td key={c} className="px-3 py-1.5 border-t border-[var(--border)] text-[oklch(0.82_0_0)] whitespace-nowrap">
                    {r[c] == null ? <span className="text-[oklch(0.35_0_0)]">—</span> : String(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 text-[12px] text-[var(--muted)]">
        <button disabled={safePage === 0} onClick={() => setPage(safePage - 1)} className="px-2 py-1 rounded border border-[var(--border-2)] disabled:opacity-40">Prev</button>
        <span>Page {safePage + 1} of {pageCount} · {filtered.length.toLocaleString()} rows</span>
        <button disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)} className="px-2 py-1 rounded border border-[var(--border-2)] disabled:opacity-40">Next</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [conv, setConv] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [c, d] = await Promise.all([api.getConversation(id), api.getDataset(id).catch(() => null)]);
        if (cancelled) return;
        setConv(c);
        setDataset(d);
      } catch {
        if (!cancelled) setError('Could not load this dashboard.');
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const pipeline = conv?.pipeline || {};
  const summary = pipeline.data_summary;
  const baseCharts = pipeline.charts || pipeline.report?.sections?.visualisations?.charts || [];
  const metrics = useMemo(() => buildMetrics(summary), [summary]);
  const [extraCharts, setExtraCharts] = useState([]);
  const [generating, setGenerating] = useState(false);

  const generateMore = async () => {
    setGenerating(true);
    try {
      const r = await api.getExtraCharts(id);
      setExtraCharts(r.charts || []);
    } catch {
      /* ignore */
    } finally {
      setGenerating(false);
    }
  };

  if (error) {
    return (
      <div className="h-screen w-screen bg-[var(--background)] text-[var(--text)] flex flex-col items-center justify-center gap-3">
        <div>{error}</div>
        <button onClick={() => navigate(`/chat/${id}`)} className="text-[var(--accent)] hover:underline">Back to chat</button>
      </div>
    );
  }

  if (!conv) {
    return (
      <div className="h-screen w-screen bg-[var(--background)] text-[var(--muted)] flex items-center justify-center gap-2">
        <Loader2 size={18} className="animate-spin" /> Loading dashboard…
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-y-auto bg-[var(--background)] text-[var(--text)]">
      <div className="max-w-[1400px] mx-auto px-6 py-5 flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(`/chat/${id}`)} className="inline-flex items-center gap-1.5 text-[var(--muted)] hover:text-[var(--text)] transition" title="Back to chat">
            <ArrowLeft size={18} strokeWidth={1.5} /> Back
          </button>
          <h1 className="text-[20px] font-semibold">{conv.title || 'Dataset dashboard'}</h1>
          <div className="ml-auto flex items-center gap-3">
            {summary && (
              <span className="text-[12px] text-[var(--muted)]">
                {summary.row_count?.toLocaleString()} rows · {summary.column_count} columns
              </span>
            )}
            <button
              onClick={() => api.exportReport(id, null, 'dashboard').catch(() => {})}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border-2)] text-[13px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition"
            >
              <Download size={14} strokeWidth={1.5} /> Export Dashboard
            </button>
          </div>
        </div>

        {/* Metrics strip */}
        {metrics.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {metrics.map((m, i) => <MetricCard key={i} {...m} />)}
          </div>
        )}

        {/* Charts */}
        <ChartArea
          charts={[...baseCharts, ...extraCharts]}
          onGenerate={generateMore}
          generating={generating}
          canGenerate={extraCharts.length === 0}
        />

        {/* Entity comparison + data table (need raw rows) */}
        {dataset?.rows?.length > 0 ? (
          <>
            <EntityComparison columns={dataset.columns} rows={dataset.rows} />
            <DataTable columns={dataset.columns} rows={dataset.rows} />
          </>
        ) : (
          <div className="text-[var(--muted)] text-sm">Raw rows unavailable for this dataset.</div>
        )}
      </div>
    </div>
  );
}
