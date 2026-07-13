'use client';

import { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import Plot from './LazyPlot';
import { Download, X, Sparkles, Globe, Pencil, ChevronUp, ChevronDown, LineChart } from 'lucide-react';

// The widget renderers + grid layout for a dashboard spec. Shared by the
// interactive editor (components/Dashboard.jsx, which passes handlers) and the
// public read-only share view (components/SharedView.jsx, which passes none).
// Every editing affordance is gated on the presence of its handler, so the
// same components render both surfaces with zero drift.

export function relativeTime(iso) {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return '';
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function RemoveButton({ onRemove, id }) {
  if (!onRemove) return null;
  return (
    <button
      onClick={() => onRemove(id)}
      className="absolute top-2 right-2 z-10 p-1 rounded text-[var(--faint)] opacity-0 group-hover:opacity-100 hover:text-[var(--danger)] hover:bg-[var(--active)] transition"
      title="Remove from dashboard"
      aria-label="Remove widget"
    >
      <X size={14} strokeWidth={1.5} />
    </button>
  );
}

// Hover strip: move up/down (+ optional edit) — sits left of the remove ✕.
function WidgetControls({ id, onMove, onEdit, widget }) {
  if (!onMove && !onEdit) return null;
  const btn = 'p-1 rounded text-[var(--faint)] opacity-0 group-hover:opacity-100 hover:text-[var(--text)] hover:bg-[var(--active)] transition';
  return (
    <div className="absolute top-2 right-8 z-10 flex">
      {onEdit && (
        <button onClick={() => onEdit(widget)} className={btn} title="Edit" aria-label="Edit widget">
          <Pencil size={13} strokeWidth={1.5} />
        </button>
      )}
      {onMove && (
        <>
          <button onClick={() => onMove(id, 'up')} className={btn} title="Move earlier" aria-label="Move widget earlier">
            <ChevronUp size={14} strokeWidth={1.5} />
          </button>
          <button onClick={() => onMove(id, 'down')} className={btn} title="Move later" aria-label="Move widget later">
            <ChevronDown size={14} strokeWidth={1.5} />
          </button>
        </>
      )}
    </div>
  );
}

function MetricCard({ widget, onRemove, onMove, onEdit }) {
  return (
    <div className="group relative flex-1 min-w-[160px] rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-4">
      <RemoveButton onRemove={onRemove} id={widget.id} />
      <WidgetControls id={widget.id} onMove={onMove} onEdit={widget.spec ? onEdit : null} widget={widget} />
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{widget.label}</div>
      <div className="text-[24px] font-bold text-[var(--text)] mt-1 tabular-nums">{widget.value}</div>
      {widget.sub && <div className="text-[11px] text-[var(--faint)] mt-0.5">{widget.sub}</div>}
    </div>
  );
}

function ChartCard({ widget, onRemove, onEdit, onMove }) {
  const spec = widget.plotly_json || {};
  return (
    <div className="group relative rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-3">
      <RemoveButton onRemove={onRemove} id={widget.id} />
      <WidgetControls id={widget.id} onMove={onMove} onEdit={widget.spec ? onEdit : null} widget={widget} />
      <div className="text-[13px] font-semibold text-[var(--muted)] mb-1 capitalize pr-6">{widget.title}</div>
      <Plot
        data={spec.data || []}
        layout={{ ...(spec.layout || {}), title: undefined, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: 'rgb(220,220,220)' }, margin: { l: 50, r: 20, t: 10, b: 40 }, height: 320, autosize: true, width: undefined }}
        style={{ width: '100%', height: '320px' }}
        useResizeHandler
        config={{ displayModeBar: false, responsive: true }}
      />
    </div>
  );
}

function TextCard({ widget, onRemove, onSave }) {
  const readOnly = !onSave;
  const [editing, setEditing] = useState(!readOnly && (!widget.text || widget.text === 'New note — click to edit.'));
  const [draft, setDraft] = useState(widget.text || '');
  const commit = () => { setEditing(false); if (draft !== widget.text) onSave(widget.id, draft); };
  return (
    <div className="group relative rounded-lg border border-dashed border-[var(--border-2)] bg-[var(--raised)] p-4">
      <RemoveButton onRemove={onRemove} id={widget.id} />
      {editing ? (
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === 'Escape') { setEditing(false); setDraft(widget.text || ''); } }}
          rows={Math.max(2, draft.split('\n').length)}
          placeholder="Write a note or heading (markdown supported)…"
          className="w-full bg-[var(--surface-input)] border border-[var(--border-2)] rounded-md px-3 py-2 text-[13px] text-[var(--text)] outline-none focus:border-[var(--accent)] resize-y"
        />
      ) : (
        <div
          className={`markdown-content text-[13px] text-[var(--muted)] pr-6 ${readOnly ? '' : 'cursor-text'}`}
          onClick={readOnly ? undefined : () => setEditing(true)}
          title={readOnly ? undefined : 'Click to edit'}
        >
          <ReactMarkdown>{widget.text || '_Empty note_'}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function InsightCard({ widget, onRemove }) {
  const [expanded, setExpanded] = useState(false);
  // Data-analysis insights (no web sources) get an analysis icon; web research
  // keeps the globe.
  const isData = !widget.sources?.length;
  const Icon = /statistical/i.test(widget.title || '') ? LineChart : isData ? Sparkles : Globe;
  return (
    <div className="group relative rounded-lg border border-[var(--border-2)] bg-[var(--raised)] p-4">
      <RemoveButton onRemove={onRemove} id={widget.id} />
      <div className="flex items-center gap-2 mb-2 pr-6">
        <Icon size={14} strokeWidth={1.5} className="text-[var(--accent)] shrink-0" />
        <div className="text-[13px] font-semibold text-[var(--text)]">{widget.title}</div>
        {widget.as_of && (
          // No locale-formatted title here: this renders under SSR on the public
          // share page, and toLocaleString() differs server-vs-browser (hydration
          // mismatch). The relative label is stable at day/hour granularity.
          <span className="text-[10.5px] text-[var(--faint)] ml-auto shrink-0">
            as of {relativeTime(widget.as_of)}
          </span>
        )}
      </div>
      <div
        className={`markdown-content text-[13px] text-[var(--muted)] overflow-hidden ${expanded ? '' : 'max-h-[130px] [mask-image:linear-gradient(to_bottom,black_60%,transparent)]'}`}
      >
        <ReactMarkdown>{widget.text || ''}</ReactMarkdown>
      </div>
      <button onClick={() => setExpanded(!expanded)} className="mt-1 text-[12px] text-[var(--accent)] hover:underline">
        {expanded ? 'Show less' : 'Show more'}
      </button>
      {widget.sources?.length > 0 && (
        <div className="mt-2 flex flex-col gap-0.5">
          {widget.sources.slice(0, 5).map((s, i) => (
            <a key={i} href={s.url} target="_blank" rel="noreferrer" className="text-[12px] text-[var(--accent)] hover:underline truncate">
              • {s.title || s.url}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity comparison (radar + stat cards) — rendered for the `comparison` widget
// ---------------------------------------------------------------------------

function EntityComparison({ columns, rows, onRemove, widgetId }) {
  const catCol = useMemo(() => columns.find((c) => rows.some((r) => typeof r[c] === 'string')) || columns[0], [columns, rows]);
  const numCols = useMemo(
    () => columns.filter((c) => rows.some((r) => typeof r[c] === 'number')).slice(0, 6),
    [columns, rows],
  );
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

  // A radar/scatterpolar needs ≥3 axes to read as a shape — with only 2 numeric
  // columns it collapses to a flat line. Below that, drop the radar and show a
  // normalized grouped bar (each metric 0–1 so scales don't dwarf each other).
  const showRadar = numCols.length >= 3;
  const barData = numCols.map((c) => ({
    type: 'bar',
    name: c,
    x: selected,
    y: selected.map((e) => norm(c, byEntity[e][c] ?? 0)),
  }));

  const statCards = (
    <div className={showRadar ? 'flex flex-col gap-2' : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2'}>
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
  );

  return (
    <div className="group relative flex flex-col gap-3">
      <RemoveButton onRemove={onRemove} id={widgetId} />
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
      {showRadar ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Plot
            data={data}
            layout={{ polar: { radialaxis: { visible: true, range: [0, 1], showticklabels: false }, bgcolor: 'rgba(0,0,0,0)' }, paper_bgcolor: 'rgba(0,0,0,0)', font: { color: 'rgb(220,220,220)' }, margin: { l: 40, r: 40, t: 20, b: 20 }, height: 340, showlegend: true, legend: { orientation: 'h', y: -0.1 } }}
            style={{ width: '100%', height: '340px' }}
            useResizeHandler
            config={{ displayModeBar: false, responsive: true }}
          />
          {statCards}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <Plot
            data={barData}
            layout={{ barmode: 'group', paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: 'rgb(220,220,220)' }, margin: { l: 40, r: 20, t: 10, b: 40 }, height: 260, yaxis: { title: 'relative (0–1)', range: [0, 1] }, showlegend: true, legend: { orientation: 'h', y: -0.2 } }}
            style={{ width: '100%', height: '260px' }}
            useResizeHandler
            config={{ displayModeBar: false, responsive: true }}
          />
          {statCards}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Data table (sortable, searchable, paginated, CSV download) — `table` widget
// ---------------------------------------------------------------------------
const PAGE_SIZE = 25;

function DataTable({ columns, rows, onRemove, widgetId }) {
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
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const onSearch = (v) => { setQuery(v); setPage(0); };
  const toggleSort = (c) => { setSort((s) => (s.col === c ? { col: c, dir: -s.dir } : { col: c, dir: 1 })); setPage(0); };

  const downloadCsv = () => {
    const esc = (v) => {
      let s = String(v ?? '');
      // CSV injection (0f): a cell beginning =, +, -, @, tab or CR runs as a
      // formula in Excel/Sheets. Neutralise by prefixing an apostrophe.
      if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
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
    <div className="group relative flex flex-col gap-2">
      <RemoveButton onRemove={onRemove} id={widgetId} />
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
// The composed grid. `handlers` is optional/partial — any missing handler
// simply hides that affordance, which is exactly how the read-only share view
// renders (pass no handlers).
// ---------------------------------------------------------------------------

export default function DashboardWidgets({ widgets = [], dataset, handlers = {} }) {
  const { onRemove, onMove, onEditMetric, onEditChart, onSaveText } = handlers;

  const metricWidgets = widgets.filter((w) => w.kind === 'metric');
  const chartWidgets = widgets.filter((w) => w.kind === 'chart');
  const insightWidgets = widgets.filter((w) => w.kind === 'insight');
  const textWidgets = widgets.filter((w) => w.kind === 'text');
  const comparisonWidget = widgets.find((w) => w.kind === 'comparison');
  const tableWidget = widgets.find((w) => w.kind === 'table');
  const hasRows = dataset?.rows?.length > 0;

  return (
    <>
      {metricWidgets.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {metricWidgets.map((w) => (
            <MetricCard key={w.id} widget={w} onRemove={onRemove} onMove={onMove} onEdit={onEditMetric} />
          ))}
        </div>
      )}

      {chartWidgets.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {chartWidgets.map((w) => (
            <ChartCard key={w.id} widget={w} onRemove={onRemove} onMove={onMove} onEdit={onEditChart} />
          ))}
        </div>
      )}

      {textWidgets.length > 0 && (
        <div className="flex flex-col gap-3">
          {textWidgets.map((w) => <TextCard key={w.id} widget={w} onRemove={onRemove} onSave={onSaveText} />)}
        </div>
      )}

      {insightWidgets.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="text-[16px] font-semibold text-[var(--text)]">Insights</div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {insightWidgets.map((w) => <InsightCard key={w.id} widget={w} onRemove={onRemove} />)}
          </div>
        </div>
      )}

      {comparisonWidget && hasRows && (
        <EntityComparison columns={dataset.columns} rows={dataset.rows} onRemove={onRemove} widgetId={comparisonWidget.id} />
      )}
      {tableWidget && hasRows && (
        <DataTable columns={dataset.columns} rows={dataset.rows} onRemove={onRemove} widgetId={tableWidget.id} />
      )}
    </>
  );
}
