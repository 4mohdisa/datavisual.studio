'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  LayoutDashboard, Telescope, BarChart3, Cable, X, Loader2,
  ArrowRight, FileText, Database, Paperclip, ClipboardList,
} from 'lucide-react';
import Button from './ui/Button';
import Input, { Select } from './ui/Input';
import ConnectSource from './ConnectSource';
import { api } from '../lib/api';

const RESEARCH_PROMPTS = [
  'Which entities lead across the key metrics, and why?',
  'Summarise the most important trends in this dataset.',
  'What does current research say about this topic?',
];

function formatDate(s) {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s || '') ? s : (s || '') + 'Z');
  if (isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function ItemCard({ conv, onOpen }) {
  const isDash = conv.mode === 'dashboard';
  const Icon = isDash ? LayoutDashboard : FileText;
  return (
    <button
      onClick={() => onOpen(conv.id)}
      className="flex items-start gap-3 rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-4 text-left hover:border-[var(--accent)] transition"
    >
      <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${isDash ? 'bg-[oklch(0.2_0.05_250)] text-[var(--accent)]' : 'bg-[var(--user-bubble)] text-[var(--muted)]'}`}>
        <Icon size={17} strokeWidth={1.5} />
      </div>
      <div className="min-w-0">
        <div className="text-[13.5px] font-medium text-[var(--text)] truncate">{conv.title || 'Untitled'}</div>
        <div className="text-[11.5px] text-[var(--faint)] mt-0.5">
          {isDash ? 'Dashboard' : 'Research report'} · {formatDate(conv.created_at)}
        </div>
      </div>
    </button>
  );
}

function Section({ title, items, onOpen }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="text-[13px] font-semibold uppercase tracking-wide text-[var(--muted)] mb-3">{title}</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((c) => <ItemCard key={c.id} conv={c} onOpen={onOpen} />)}
      </div>
    </div>
  );
}

// The workspace home — a dedicated hub for the two product flows (dashboards
// and deep research) plus the user's existing work. Not a chat surface: the
// research composer lives inside its card, and dashboards are one click away.
export default function Home({
  conversations,
  currentFile,
  currentMatchFile,
  onFileUploaded,
  onRemoveFile,
  onStartResearch,
  onOpenItem,
}) {
  const router = useRouter();
  const fileInputRef = useRef(null);
  // Which slot the next file-dialog selection fills: 'main' (dataset) or
  // 'match' (optional match-history CSV that enables the XGBoost model).
  const uploadTargetRef = useRef('main');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [connectOpen, setConnectOpen] = useState(false);
  const [question, setQuestion] = useState('');

  // A "Dig deeper" follow-up from a report lands here as ?q=… — prefill the
  // research composer so the user just hits Start.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q');
    if (q) {
      setQuestion(q);
      window.history.replaceState(null, '', '/studio');
    }
  }, []);
  const [creating, setCreating] = useState(false);
  const [template, setTemplate] = useState('overview');
  const [focus, setFocus] = useState('');

  const pickFile = (kind) => {
    uploadTargetRef.current = kind;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError('');
    setUploading(true);
    try {
      onFileUploaded(await api.uploadFile(file), uploadTargetRef.current);
    } catch (err) {
      setError(err?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleCreateDashboard = async () => {
    if (!currentFile || creating) return;
    setCreating(true);
    setError('');
    try {
      const r = await api.createDashboard(currentFile.file_id, currentFile.filename, template, focus);
      onRemoveFile('main');
      router.push(`/dashboard/${r.conversation_id}`);
    } catch (err) {
      setError(err?.message || 'Could not create the dashboard');
      setCreating(false);
    }
  };

  const startResearch = () => {
    const q = question.trim();
    if (q) onStartResearch(q);
  };

  const dashboards = conversations.filter((c) => c.mode === 'dashboard').slice(0, 9);
  const research = conversations.filter((c) => c.mode !== 'dashboard').slice(0, 9);

  return (
    <div className="flex-1 h-screen overflow-y-auto bg-[var(--background)]">
      <div className="max-w-[1060px] mx-auto px-8 py-12 flex flex-col gap-10">
        {/* Hero */}
        <div>
          <h1 className="text-[26px] font-semibold text-[var(--text)] m-0">datavisual.studio</h1>
          <p className="text-[14px] text-[var(--muted)] mt-1.5 m-0">
            Turn data into live dashboards and deeply-researched reports.
          </p>
        </div>

        {/* The two flows */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Build a dashboard */}
          <div className="rounded-2xl border border-[var(--border-2)] bg-[var(--raised)] p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-[oklch(0.2_0.05_250)] flex items-center justify-center">
                <LayoutDashboard size={18} strokeWidth={1.5} className="text-[var(--accent)]" />
              </div>
              <div>
                <div className="text-[15px] font-semibold text-[var(--text)]">Build a dashboard</div>
                <div className="text-[12px] text-[var(--faint)]">No AI cost · instant</div>
              </div>
            </div>
            <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0">
              Metrics, interactive charts and a data table from any dataset. Refine it by
              chatting with the dashboard assistant, and refresh connected sources anytime.
            </p>

            {currentFile ? (
              <div className="flex flex-col gap-3 mt-auto">
                <div className="inline-flex items-center gap-2 self-start px-3 py-1.5 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-sm text-[var(--text)]">
                  <BarChart3 size={15} strokeWidth={1.5} />
                  <span className="font-medium">{currentFile.filename}</span>
                  <span className="text-[11px] text-[var(--faint)]">
                    {currentFile.rows?.toLocaleString?.()} rows
                  </span>
                  <button onClick={() => onRemoveFile('main')} aria-label="Remove dataset" className="text-[var(--muted)] hover:text-[var(--danger)]">
                    <X size={14} strokeWidth={1.5} />
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="primary" onClick={handleCreateDashboard} disabled={creating}>
                    {creating ? <Loader2 size={15} className="animate-spin" /> : <LayoutDashboard size={15} strokeWidth={1.5} />}
                    {creating ? 'Building dashboard…' : 'Create dashboard'}
                    {!creating && <ArrowRight size={15} strokeWidth={1.5} />}
                  </Button>
                  <Select
                    value={template}
                    onChange={(e) => setTemplate(e.target.value)}
                    options={[
                      { value: 'overview', label: 'Overview — metrics + 6 charts' },
                      { value: 'minimal', label: 'Minimal — metrics + 2 charts' },
                      { value: 'full', label: 'Full — everything' },
                      { value: 'kpi', label: 'KPI — metrics-heavy, 3 charts' },
                      { value: 'visual', label: 'Visual — charts only, no table' },
                    ]}
                    className="w-auto text-[12.5px] py-1.5"
                    title="Dashboard template — you can always add more later"
                  />
                  {(currentFile.column_names || []).length > 0 && (
                    <Select
                      value={focus}
                      onChange={(e) => setFocus(e.target.value)}
                      options={[
                        { value: '', label: 'Focus: auto' },
                        ...currentFile.column_names.map((c) => ({ value: c, label: `Focus: ${c}` })),
                      ]}
                      className="w-auto text-[12.5px] py-1.5"
                      title="Which numeric column the headline metric and first charts should centre on"
                    />
                  )}
                </div>
                <div className="text-[12px] text-[var(--faint)]">
                  …or run deep research on this dataset from the card on the right.
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2 mt-auto">
                <Button onClick={() => pickFile('main')} disabled={uploading}>
                  {uploading ? <Loader2 size={15} className="animate-spin" /> : <BarChart3 size={15} strokeWidth={1.5} />}
                  {uploading ? 'Uploading…' : 'Upload dataset'}
                </Button>
                <Button variant="outline" onClick={() => setConnectOpen(true)}>
                  <Cable size={15} strokeWidth={1.5} /> Connect database / API
                </Button>
              </div>
            )}
            {error && <div className="text-[12px] text-[var(--danger)]">{error}</div>}
          </div>

          {/* Deep research */}
          <div className="rounded-2xl border border-[var(--border-2)] bg-[var(--raised)] p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-[oklch(0.22_0.05_150)] flex items-center justify-center">
                <Telescope size={18} strokeWidth={1.5} className="text-[oklch(0.75_0.15_150)]" />
              </div>
              <div>
                <div className="text-[15px] font-semibold text-[var(--text)]">Deep research</div>
                <div className="text-[12px] text-[var(--faint)]">Live web research + AI council · ~2 min</div>
              </div>
            </div>
            <p className="text-[13px] text-[var(--muted)] leading-relaxed m-0">
              Multiple AI models independently analyse your question (and dataset), peer-review
              each other, and a chairman synthesises a cited report. The findings land on a
              dashboard automatically.
            </p>

            <div className="flex flex-col gap-2 mt-auto">
              {(currentFile || currentMatchFile) && (
                <div className="flex flex-wrap items-center gap-1.5">
                  {currentFile && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-[12px] text-[var(--text)]">
                      <Database size={12} strokeWidth={1.5} className="text-[var(--accent)]" />
                      {currentFile.filename}
                      <button onClick={() => onRemoveFile('main')} aria-label="Remove dataset" className="text-[var(--muted)] hover:text-[var(--danger)]">
                        <X size={12} strokeWidth={1.5} />
                      </button>
                    </span>
                  )}
                  {currentMatchFile && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-[12px] text-[var(--text)]">
                      <ClipboardList size={12} strokeWidth={1.5} />
                      {currentMatchFile.filename}
                      <span className="text-[10px] text-[var(--faint)]">match history</span>
                      <button onClick={() => onRemoveFile('match')} aria-label="Remove match history" className="text-[var(--muted)] hover:text-[var(--danger)]">
                        <X size={12} strokeWidth={1.5} />
                      </button>
                    </span>
                  )}
                </div>
              )}
              <Input
                as="textarea"
                rows={2}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); startResearch(); } }}
                placeholder={currentFile ? 'What do you want to know about this data?' : 'What do you want to research?'}
                className="resize-none"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="primary" onClick={startResearch} disabled={!question.trim()}>
                  <Telescope size={15} strokeWidth={1.5} /> Start research
                </Button>
                <Button
                  variant="outline"
                  onClick={() => pickFile(currentFile ? 'match' : 'main')}
                  disabled={uploading || (!!currentFile && !!currentMatchFile)}
                  title={!currentFile
                    ? 'Attach a dataset for the research to analyse'
                    : !currentMatchFile
                    ? 'Attach an optional match-history CSV (enables the XGBoost model)'
                    : 'Both files attached'}
                >
                  {uploading ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={14} strokeWidth={1.5} />}
                  {!currentFile ? 'Attach data' : 'Add match history'}
                </Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {RESEARCH_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => setQuestion(p)}
                    className="px-2.5 py-1 rounded-full border border-[var(--border-2)] text-[11.5px] text-[var(--faint)] hover:text-[var(--text)] hover:border-[var(--border-3)] transition"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Existing work */}
        <Section title="Your dashboards" items={dashboards} onOpen={onOpenItem} />
        <Section title="Research reports" items={research} onOpen={onOpenItem} />
        {dashboards.length === 0 && research.length === 0 && (
          <div className="text-[13px] text-[var(--faint)]">
            Nothing here yet — build your first dashboard or start a research run above.
          </div>
        )}
      </div>

      <input ref={fileInputRef} type="file" accept=".csv,.xls,.xlsx,.json" onChange={handleFileChange} className="hidden" />
      {connectOpen && (
        <ConnectSource
          onImported={(result) => onFileUploaded(result, 'main')}
          onClose={() => setConnectOpen(false)}
        />
      )}
    </div>
  );
}
