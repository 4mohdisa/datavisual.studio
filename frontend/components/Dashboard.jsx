'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import Input from './ui/Input';
import Skeleton from './ui/Skeleton';
import { ArrowLeft, Download, Loader2, X, Sparkles, Send, PanelRightClose, PanelRightOpen, RefreshCw, Pencil, Plus, Hash, Check, LayoutGrid, BarChart3, Wand2, Share2 } from 'lucide-react';
import WidgetEditor from './WidgetEditor';
import ShareModal from './ShareModal';
import DashboardWidgets, { relativeTime } from './DashboardWidgets';
import ExportDashboardButton from './ExportDashboardButton';
import Button from './ui/Button';
import Modal from './ui/Modal';
import { api } from '../lib/api';
import { busyLabel as guessBusyLabel } from '../lib/intent';

// ---------------------------------------------------------------------------
// Dashboard assistant — chat panel that edits the dashboard in place
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  'Which region has the highest revenue?',
  'Add 3 more useful charts',
  'Add a total metric for the main value column',
  'Research this topic online and pin the findings',
];

// Honest status copy is derived from `../lib/intent` (guessBusyLabel), which
// mirrors the backend classify_intent so the spinner never names the wrong
// action — e.g. "Updating the dashboard…" while the server is answering a
// question. See lib/intent.test.js.

// Show the working (Phase 0e): the executed query + the result the answer was
// phrased from, collapsed by default. Transparency is the feature — if the user
// can see SUM(mrr) over 18 rows they catch the error instantly.
function Working({ working }) {
  if (!working || (!working.columns && !working.warning)) return null;
  const { spec, columns, rows, warning } = working;
  const summarize = (s) => {
    if (!s) return 'selected rows';
    const parts = [];
    if (s.filter?.length) parts.push('filter ' + s.filter.map((f) => `${f.column} ${f.op} ${f.value}`).join(', '));
    if (s.group_by?.length) parts.push('group by ' + s.group_by.join(', '));
    if (s.agg) parts.push(Object.entries(s.agg).map(([k, v]) => `${v}(${k})`).join(', '));
    return parts.join(' · ') || 'selected rows';
  };
  return (
    <details className="self-start w-full text-[12px] text-[var(--muted)] rounded-lg border border-[var(--border)] bg-[var(--raised)]">
      <summary className="cursor-pointer select-none px-3 py-2 hover:text-[var(--text)]">Show the working</summary>
      <div className="flex flex-col gap-2 px-3 pb-3">
        {warning && (
          <div className="rounded-md border border-[var(--warning)] px-2 py-1.5 text-[var(--warning)] leading-snug">{warning}</div>
        )}
        <div><span className="text-[var(--faint)]">Query:</span> {summarize(spec)}</div>
        {columns?.length > 0 && rows?.length > 0 && (
          <div className="overflow-x-auto">
            <table className="border-collapse text-[11.5px]">
              <thead>
                <tr>{columns.map((c) => <th key={c} className="border-b border-[var(--border)] px-2 py-1 text-left font-medium">{c}</th>)}</tr>
              </thead>
              <tbody>
                {rows.slice(0, 8).map((r, i) => (
                  <tr key={i}>{columns.map((c) => <td key={c} className="border-b border-[var(--border)] px-2 py-1">{String(r[c])}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  );
}

function AssistantPanel({ history, busy, busyLabel, working, onSend, onClose, pinOp, onPin }) {
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
    <section aria-label="Dashboard assistant" className="fixed inset-0 z-[50] w-full lg:relative lg:inset-auto lg:z-auto lg:w-[360px] shrink-0 h-screen flex flex-col border-l border-[var(--border)] bg-[var(--background)]">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <Sparkles size={15} strokeWidth={1.5} className="text-[var(--accent)]" />
        <h2 className="text-sm font-semibold text-[var(--text)]">Dashboard assistant</h2>
        <button onClick={onClose} className="ml-auto p-1 rounded text-[var(--muted)] hover:text-[var(--text)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]" aria-label="Close assistant">
          <PanelRightClose size={16} strokeWidth={1.5} />
        </button>
      </div>

      {/* Answers arrive asynchronously — a live region announces them (and the
          busy status) to screen readers, which otherwise get nothing (Phase 4d). */}
      <div ref={scrollRef} aria-live="polite" className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
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
            tabIndex={h.role === 'assistant' ? 0 : undefined}
            className={`max-w-[92%] rounded-lg px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] ${
              h.role === 'user'
                ? 'self-end bg-[var(--user-bubble)] text-[var(--text)]'
                : 'self-start bg-[var(--raised)] border border-[var(--border)] text-[var(--muted)]'
            }`}
          >
            {h.content}
          </div>
        ))}
        {!busy && <Working working={working} />}
        {busy && (
          <div role="status" className="self-start flex items-center gap-2 text-[13px] text-[var(--muted)]">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" /> {busyLabel || 'Working…'}
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

      {pinOp && (
        <button
          onClick={onPin}
          disabled={busy}
          className="mx-3 mb-2 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--accent)] text-[12.5px] text-[var(--accent)] hover:bg-[var(--active)] transition disabled:opacity-50"
        >
          <Plus size={13} strokeWidth={1.5} /> Pin this answer as a {pinOp.op === 'add_metric' ? 'metric' : 'chart'}
        </button>
      )}

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="flex items-center gap-2 p-3 border-t border-[var(--border)]"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the data, or say what to add"
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
    </section>
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
  const [shareId, setShareId] = useState(null);
  const [shareOpen, setShareOpen] = useState(false);

  // On phones the assistant is a full-screen overlay, so open it lands users on
  // the assistant, not their dashboard. Start it closed below lg; desktop keeps
  // the side panel open. (Runs once on mount — SSR/first paint stays open to
  // match hydration, then corrects.)
  useEffect(() => {
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches) {
      setPanelOpen(false);
    }
  }, []);

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
        setShareId(c.share_id || null);
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
    setPending(message);
    setWorking(null);
    // Optimistic: show the user's message immediately; the server response
    // carries the authoritative history (both turns) and replaces it.
    setConv((prev) => prev ? {
      ...prev,
      dashboard: { ...prev.dashboard, history: [...(prev.dashboard?.history || []), { role: 'user', content: message }] },
    } : prev);
    try {
      const result = await api.dashboardChat(id, { message });
      applyResult(result);
      setWorking(result.working || null);
      // An answered question can carry a spec to pin as a widget (the product moment).
      setPinOp(result.pin_op || null);
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

  // A pinnable spec returned by the last answered question (null = nothing to pin).
  const [pinOp, setPinOp] = useState(null);
  const [pending, setPending] = useState('');   // last-sent message (drives honest status)
  const [working, setWorking] = useState(null);  // show-the-working for the last answer
  const handlePin = async () => {
    if (!pinOp) return;
    const op = pinOp;
    setPinOp(null);
    try {
      applyResult(await api.dashboardChat(id, { ops: [op] }));
    } catch { setPinOp(op); /* restore so they can retry */ }
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

  // Sync is possible when there's a live data source OR a pinned research topic.
  const canSync = !!conv.file?.source || widgets.some((w) => w.kind === 'insight' && w.query);

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[var(--background)] text-[var(--text)]">
      <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto outline-none">
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
                onClick={() => setShareOpen(true)}
                title="Create a public, read-only link to this dashboard"
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-[13px] transition ${
                  shareId
                    ? 'border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--active)]'
                    : 'border-[var(--border-2)] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)]'
                }`}
              >
                <Share2 size={14} strokeWidth={1.5} /> {shareId ? 'Shared' : 'Share'}
              </button>
              <ExportDashboardButton conversationId={id} />
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

          {/* Widgets (shared read-only-capable renderer) */}
          <DashboardWidgets
            widgets={widgets}
            dataset={dataset}
            handlers={{
              onRemove: handleRemove,
              onMove: handleMove,
              onEditMetric: (widget) => setEditor({ mode: 'metric', widget }),
              onEditChart: (widget) => setEditor({ mode: 'chart', widget }),
              onSaveText: handleSaveText,
            }}
          />

          {widgets.length === 0 && (
            <div className="text-[var(--muted)] text-sm">
              This dashboard is empty — ask the assistant to add charts, metrics, or research.
            </div>
          )}
        </div>
      </main>

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
      {shareOpen && (
        <ShareModal
          conversationId={id}
          shareId={shareId}
          onChange={setShareId}
          onClose={() => setShareOpen(false)}
        />
      )}
      {panelOpen && (
        <AssistantPanel
          history={dashboard.history || []}
          busy={busy}
          busyLabel={busy ? guessBusyLabel(pending) : ''}
          working={working}
          onSend={handleSend}
          onClose={() => setPanelOpen(false)}
          pinOp={pinOp}
          onPin={handlePin}
        />
      )}
    </div>
  );
}
