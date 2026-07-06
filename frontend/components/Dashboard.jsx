'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import Plot from './LazyPlot';
import Input from './ui/Input';
import Skeleton from './ui/Skeleton';
import { ArrowLeft, Download, Loader2, X, Sparkles, Send, PanelRightClose, PanelRightOpen, Globe, RefreshCw, Pencil, Plus, Hash, ChevronUp, ChevronDown, Check, LayoutGrid, BarChart3, Wand2, LineChart } from 'lucide-react';
import WidgetEditor from './WidgetEditor';
import Button from './ui/Button';
import Modal from './ui/Modal';
import { api } from '../lib/api';

function relativeTime(iso) {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return '';
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// ---------------------------------------------------------------------------
// Widget renderers
// ---------------------------------------------------------------------------

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
  const [editing, setEditing] = useState(!widget.text || widget.text === 'New note — click to edit.');
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
        <div className="markdown-content text-[13px] text-[var(--muted)] cursor-text pr-6" onClick={() => setEditing(true)} title="Click to edit">
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
          <span className="text-[10.5px] text-[var(--faint)] ml-auto shrink-0" title={new Date(widget.as_of).toLocaleString()}>
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
// Dashboard assistant — chat panel that edits the dashboard in place
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  'Add 3 more useful charts',
  'Add a total metric for the main value column',
  'Research this topic online and pin the findings',
];

function AssistantPanel({ history, busy, onSend, onClose }) {
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history, busy]);

  const send = (text) => {
    const t = (text || input).trim();
    if (!t || busy) return;
    setInput('');
    onSend(t);
  };

  return (
    <div className="w-[360px] shrink-0 h-screen flex flex-col border-l border-[var(--border)] bg-[var(--background)]">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <Sparkles size={15} strokeWidth={1.5} className="text-[var(--accent)]" />
        <div className="text-sm font-semibold text-[var(--text)]">Dashboard assistant</div>
        <button onClick={onClose} className="ml-auto p-1 rounded text-[var(--muted)] hover:text-[var(--text)]" aria-label="Close assistant">
          <PanelRightClose size={16} strokeWidth={1.5} />
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {history.length === 0 && (
          <div className="text-[13px] text-[var(--muted)] leading-relaxed">
            Edit this dashboard by chatting — add or change charts and metrics,
            remove widgets, or pull in live research. Changes apply to this
            dashboard in place.
          </div>
        )}
        {history.map((h, i) => (
          <div
            key={i}
            className={`max-w-[92%] rounded-lg px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap ${
              h.role === 'user'
                ? 'self-end bg-[var(--user-bubble)] text-[var(--text)]'
                : 'self-start bg-[var(--raised)] border border-[var(--border)] text-[var(--muted)]'
            }`}
          >
            {h.content}
          </div>
        ))}
        {busy && (
          <div className="self-start flex items-center gap-2 text-[13px] text-[var(--muted)]">
            <Loader2 size={14} className="animate-spin" /> Updating dashboard…
          </div>
        )}
      </div>

      {history.length === 0 && (
        <div className="px-4 pb-2 flex flex-col gap-1.5">
          {SUGGESTIONS.map((sugg) => (
            <button
              key={sugg}
              onClick={() => send(sugg)}
              disabled={busy}
              className="text-left px-3 py-2 rounded-lg bg-[var(--raised)] border border-[var(--border)] text-[12px] text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--border-2)] transition disabled:opacity-50"
            >
              {sugg}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="flex items-center gap-2 p-3 border-t border-[var(--border)]"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. add a pie of revenue by product"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center bg-white text-black hover:bg-[oklch(0.88_0_0)] transition disabled:opacity-40"
          aria-label="Send"
        >
          <Send size={15} strokeWidth={1.5} />
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

export default function Dashboard({ id }) {
  const router = useRouter();
  const [conv, setConv] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let c = await api.getConversation(id);
        // Records that predate the widget spec: build it once, in place.
        if (!c.dashboard && (c.file || c.pipeline?.charts?.length || c.pipeline?.data_summary)) {
          await api.ensureDashboard(id).catch(() => {});
          c = await api.getConversation(id);
        }
        const d = await api.getDataset(id).catch(() => null);
        if (cancelled) return;
        setConv(c);
        setDataset(d);
      } catch {
        if (!cancelled) setError('Could not load this dashboard.');
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const dashboard = conv?.dashboard || { widgets: [], history: [] };
  const widgets = dashboard.widgets || [];
  const backHref = conv?.mode === 'dashboard' ? '/studio' : `/chat/${id}`;
  const summary = conv?.pipeline?.data_summary;

  const applyResult = (result) => {
    setConv((prev) => (prev ? { ...prev, dashboard: result.dashboard, title: result.dashboard.title || prev.title } : prev));
  };

  const handleSend = async (message) => {
    setBusy(true);
    // Optimistic: show the user's message immediately; the server response
    // carries the authoritative history (both turns) and replaces it.
    setConv((prev) => prev ? {
      ...prev,
      dashboard: { ...prev.dashboard, history: [...(prev.dashboard?.history || []), { role: 'user', content: message }] },
    } : prev);
    try {
      applyResult(await api.dashboardChat(id, { message }));
    } catch (e) {
      setConv((prev) => prev ? {
        ...prev,
        dashboard: {
          ...prev.dashboard,
          history: [...(prev.dashboard?.history || []), { role: 'assistant', content: e.message || 'Edit failed.' }],
        },
      } : prev);
    } finally {
      setBusy(false);
    }
  };

  const [refreshing, setRefreshing] = useState(false);
  // Manual widget editor: {mode: 'chart'|'metric', widget?} — widget set = edit.
  const [editor, setEditor] = useState(null);
  // Inline title rename (null = not renaming, string = draft value).
  const [titleDraft, setTitleDraft] = useState(null);

  const commitTitle = async () => {
    const t = (titleDraft || '').trim();
    setTitleDraft(null);
    if (!t || t === dashboard.title) return;
    try {
      applyResult(await api.dashboardChat(id, { ops: [{ op: 'rename_dashboard', title: t }] }));
    } catch { /* keep old title */ }
  };

  const handleEditorSubmit = async (spec) => {
    setBusy(true);
    try {
      const ops = editor.widget
        ? [{ op: editor.mode === 'metric' ? 'update_metric' : 'update_chart', id: editor.widget.id, ...spec }]
        : [{ op: editor.mode === 'metric' ? 'add_metric' : 'add_chart', ...spec }];
      applyResult(await api.dashboardChat(id, { ops }));
      setEditor(null);
    } catch (e) {
      alert(e.message || 'Edit failed');
    } finally {
      setBusy(false);
    }
  };

  // Prebuilt components gallery: {open, items, loading}.
  const [gallery, setGallery] = useState(null);

  const openGallery = async () => {
    setGallery({ items: [], loading: true });
    try {
      const r = await api.dashboardSuggestions(id);
      setGallery({ items: r.suggestions || [], loading: false });
    } catch {
      setGallery({ items: [], loading: false });
    }
  };

  const addComponent = async (item) => {
    setGallery((g) => g && { ...g, items: g.items.filter((i) => i !== item) });
    try {
      applyResult(await api.dashboardChat(id, { ops: [item.op] }));
    } catch { /* suggestion already removed from list; harmless */ }
  };

  const handleMove = async (widgetId, direction) => {
    try {
      applyResult(await api.dashboardChat(id, { ops: [{ op: 'move_widget', id: widgetId, direction }] }));
    } catch { /* leave as-is */ }
  };

  const [analyzing, setAnalyzing] = useState(false);
  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      // Free statistical read + AI key findings in one click.
      applyResult(await api.dashboardChat(id, { ops: [{ op: 'add_analysis' }, { op: 'add_key_findings' }] }));
    } catch (e) {
      alert(e.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSaveText = (wid, text) =>
    api.dashboardChat(id, { ops: [{ op: 'update_text', id: wid, text }] }).then(applyResult).catch(() => {});
  // The living-monitor "Update": re-pull data + re-run pinned research, then
  // surface exactly what changed.
  const [syncResult, setSyncResult] = useState(null);
  const handleSync = async () => {
    setRefreshing(true);
    try {
      const r = await api.syncDashboard(id);
      const [c, d] = await Promise.all([api.getConversation(id), api.getDataset(id).catch(() => null)]);
      setConv(c);
      setDataset(d);
      setSyncResult({ changes: r.changes || [], at: r.synced_at });
    } catch (e) {
      setSyncResult({ error: e.message || 'Update failed' });
    } finally {
      setRefreshing(false);
    }
  };

  const handleRemove = async (widgetId) => {
    setBusy(true);
    try {
      applyResult(await api.dashboardChat(id, { ops: [{ op: 'remove_widget', id: widgetId }] }));
    } catch { /* leave as-is */ } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <div className="h-screen w-screen bg-[var(--background)] text-[var(--text)] flex flex-col items-center justify-center gap-3">
        <div>{error}</div>
        <button onClick={() => router.push(backHref)} className="text-[var(--accent)] hover:underline">Back</button>
      </div>
    );
  }

  if (!conv) {
    return (
      <div className="h-screen w-screen bg-[var(--background)] p-6 flex flex-col gap-4">
        <Skeleton className="h-[36px] w-[420px]" />
        <div className="flex gap-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[90px] flex-1" />)}</div>
        <div className="grid grid-cols-2 gap-3 flex-1">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[300px]" />)}</div>
      </div>
    );
  }

  const metricWidgets = widgets.filter((w) => w.kind === 'metric');
  const chartWidgets = widgets.filter((w) => w.kind === 'chart');
  const insightWidgets = widgets.filter((w) => w.kind === 'insight');
  const textWidgets = widgets.filter((w) => w.kind === 'text');
  const comparisonWidget = widgets.find((w) => w.kind === 'comparison');
  const tableWidget = widgets.find((w) => w.kind === 'table');
  const hasRows = dataset?.rows?.length > 0;
  // Sync is possible when there's a live data source OR a pinned research topic.
  const canSync = !!conv.file?.source || insightWidgets.some((w) => w.query);

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[var(--background)] text-[var(--text)]">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1400px] mx-auto px-6 py-5 flex flex-col gap-6">
          {/* Header */}
          <div className="flex items-center gap-3">
            <button onClick={() => router.push(backHref)} className="inline-flex items-center gap-1.5 text-[var(--muted)] hover:text-[var(--text)] transition" title="Back">
              <ArrowLeft size={18} strokeWidth={1.5} /> Back
            </button>
            {titleDraft !== null ? (
              <div className="flex items-center gap-1.5">
                <input
                  autoFocus
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitTitle();
                    else if (e.key === 'Escape') setTitleDraft(null);
                  }}
                  onBlur={commitTitle}
                  className="bg-[var(--surface-input)] border border-[var(--border-2)] rounded-md px-2.5 py-1 text-[18px] font-semibold text-[var(--text)] outline-none focus:border-[var(--accent)] min-w-[280px]"
                />
                <button onClick={commitTitle} className="p-1 text-[var(--muted)] hover:text-[var(--text)]" aria-label="Save title">
                  <Check size={16} strokeWidth={1.5} />
                </button>
              </div>
            ) : (
              <h1
                className="group/title text-[20px] font-semibold truncate cursor-text flex items-center gap-2"
                onClick={() => setTitleDraft(dashboard.title || conv.title || 'Dashboard')}
                title="Click to rename"
              >
                {dashboard.title || conv.title || 'Dashboard'}
                <Pencil size={13} strokeWidth={1.5} className="shrink-0 text-[var(--faint)] opacity-0 group-hover/title:opacity-100 transition" />
              </h1>
            )}
            <div className="ml-auto flex items-center gap-3">
              {dashboard.last_synced && (
                <span className="text-[12px] text-[var(--faint)]" title={new Date(dashboard.last_synced).toLocaleString()}>
                  Updated {relativeTime(dashboard.last_synced)}
                </span>
              )}
              {canSync && (
                <button
                  onClick={handleSync}
                  disabled={refreshing}
                  title="Re-pull the latest data and re-run pinned research, then show what changed"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition disabled:opacity-50"
                >
                  <RefreshCw size={14} strokeWidth={1.5} className={refreshing ? 'animate-spin' : ''} />
                  {refreshing ? 'Updating…' : 'Update'}
                </button>
              )}
              <button
                onClick={() => api.exportReport(id, null, 'dashboard').catch(() => {})}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border-2)] text-[13px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition"
              >
                <Download size={14} strokeWidth={1.5} /> Export
              </button>
              {!panelOpen && (
                <button
                  onClick={() => setPanelOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-[var(--border-2)] text-[13px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition"
                >
                  <PanelRightOpen size={14} strokeWidth={1.5} /> Edit with AI
                </button>
              )}
            </div>
          </div>

          {/* What changed — the living-monitor payoff */}
          {syncResult && (
            <div className="rounded-xl border border-[var(--border-2)] bg-[oklch(0.16_0.02_250)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <RefreshCw size={14} strokeWidth={1.5} className="text-[var(--accent)]" />
                <span className="text-[13px] font-semibold text-[var(--text)]">
                  {syncResult.error ? 'Update failed' : 'What changed'}
                </span>
                <span className="text-[11px] text-[var(--faint)]">
                  {syncResult.at ? relativeTime(syncResult.at) : ''}
                </span>
                <button onClick={() => setSyncResult(null)} className="ml-auto p-1 text-[var(--muted)] hover:text-[var(--text)]" aria-label="Dismiss">
                  <X size={14} strokeWidth={1.5} />
                </button>
              </div>
              {syncResult.error ? (
                <p className="text-[13px] text-[var(--danger)] m-0">{syncResult.error}</p>
              ) : syncResult.changes.length ? (
                <ul className="flex flex-col gap-1 m-0 pl-0 list-none">
                  {syncResult.changes.map((c, i) => (
                    <li key={i} className="markdown-content text-[13px] text-[var(--muted)] flex gap-2">
                      <span className="text-[var(--accent)]">•</span>
                      <span><ReactMarkdown components={{ p: 'span' }}>{c}</ReactMarkdown></span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] text-[var(--muted)] m-0">Everything is up to date — no changes since last check.</p>
              )}
            </div>
          )}

          {/* Manual editing toolbar */}
          {(summary?.columns?.length > 0) && (
            <div className="flex flex-wrap items-center gap-2 -mb-2">
              <Button size="sm" variant="outline" onClick={openGallery}>
                <LayoutGrid size={13} strokeWidth={1.5} /> Components
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditor({ mode: 'chart' })}>
                <Plus size={13} strokeWidth={1.5} /> Add chart
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditor({ mode: 'metric' })}>
                <Hash size={13} strokeWidth={1.5} /> Add metric
              </Button>
              <Button size="sm" variant="primary" onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} strokeWidth={1.5} />}
                {analyzing ? 'Analysing…' : 'Analyze data'}
              </Button>
              <span className="text-[11.5px] text-[var(--faint)]">
                …or ask the assistant. Hover a chart to edit or remove it.
              </span>
            </div>
          )}

          {/* Metrics strip */}
          {metricWidgets.length > 0 && (
            <div className="flex flex-wrap gap-3">
              {metricWidgets.map((w) => <MetricCard key={w.id} widget={w} onRemove={handleRemove} onMove={handleMove} onEdit={(widget) => setEditor({ mode: 'metric', widget })} />)}
            </div>
          )}

          {/* Charts grid */}
          {chartWidgets.length > 0 && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              {chartWidgets.map((w) => <ChartCard key={w.id} widget={w} onRemove={handleRemove} onMove={handleMove} onEdit={(widget) => setEditor({ mode: 'chart', widget })} />)}
            </div>
          )}

          {/* Text notes */}
          {textWidgets.length > 0 && (
            <div className="flex flex-col gap-3">
              {textWidgets.map((w) => (
                <TextCard key={w.id} widget={w} onRemove={handleRemove} onSave={handleSaveText} />
              ))}
            </div>
          )}

          {/* Research + AI insights */}
          {insightWidgets.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="text-[16px] font-semibold text-[var(--text)]">Insights</div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {insightWidgets.map((w) => <InsightCard key={w.id} widget={w} onRemove={handleRemove} />)}
              </div>
            </div>
          )}

          {widgets.length === 0 && (
            <div className="text-[var(--muted)] text-sm">
              This dashboard is empty — ask the assistant to add charts, metrics, or research.
            </div>
          )}

          {comparisonWidget && hasRows && (
            <EntityComparison columns={dataset.columns} rows={dataset.rows} onRemove={handleRemove} widgetId={comparisonWidget.id} />
          )}
          {tableWidget && hasRows && (
            <DataTable columns={dataset.columns} rows={dataset.rows} onRemove={handleRemove} widgetId={tableWidget.id} />
          )}
        </div>
      </div>

      {gallery && (
        <Modal title="Add components" onClose={() => setGallery(null)} width="w-[560px]">
          <p className="text-[12.5px] text-[var(--faint)] -mt-2 mb-4">
            Prebuilt from your dataset's columns — one click to add, no regeneration.
          </p>
          {gallery.loading ? (
            <div className="flex items-center gap-2 text-[13px] text-[var(--muted)] py-6">
              <Loader2 size={14} className="animate-spin" /> Analysing your columns…
            </div>
          ) : gallery.items.length === 0 ? (
            <div className="text-[13px] text-[var(--muted)] py-6">
              Everything we can prebuild is already on this dashboard — use Add chart
              or the assistant for custom widgets.
            </div>
          ) : (
            ['analysis', 'chart', 'metric', 'section'].map((kind) => {
              const items = gallery.items.filter((i) => i.kind === kind);
              if (!items.length) return null;
              const label = { analysis: 'Analysis', chart: 'Charts', metric: 'Metrics', section: 'Sections' }[kind];
              const Icon = { analysis: Wand2, chart: BarChart3, metric: Hash, section: LayoutGrid }[kind];
              return (
                <div key={kind} className="mb-4">
                  <div className="text-[11.5px] font-semibold uppercase tracking-wide text-[var(--muted)] mb-2">{label}</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {items.map((item, i) => (
                      <button
                        key={i}
                        onClick={() => addComponent(item)}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--border-2)] bg-[var(--raised)] text-left hover:border-[var(--accent)] transition"
                      >
                        <Icon size={14} strokeWidth={1.5} className="shrink-0 text-[var(--accent)]" />
                        <span className="min-w-0 flex-1">
                          <span className="block text-[12.5px] text-[var(--text)] truncate">{item.label}</span>
                          {item.detail && <span className="block text-[10.5px] text-[var(--faint)]">{item.detail}</span>}
                        </span>
                        <Plus size={13} strokeWidth={1.5} className="shrink-0 text-[var(--muted)]" />
                      </button>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </Modal>
      )}
      {editor && (
        <WidgetEditor
          mode={editor.mode}
          columns={summary?.columns || []}
          initial={editor.widget?.spec || null}
          busy={busy}
          onSubmit={handleEditorSubmit}
          onClose={() => setEditor(null)}
        />
      )}
      {panelOpen && (
        <AssistantPanel
          history={dashboard.history || []}
          busy={busy}
          onSend={handleSend}
          onClose={() => setPanelOpen(false)}
        />
      )}
    </div>
  );
}
