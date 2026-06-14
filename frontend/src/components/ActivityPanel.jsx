import { useState, useEffect, useRef, useMemo } from 'react';
import { X, BarChart3, TrendingUp, CheckCircle2, AlertCircle } from 'lucide-react';

const TITLE = {
  dataset_analysed: 'Analysing the dataset',
  charts_generated: 'Generating visualisations',
  search_started: 'Searching the web',
  search_complete: 'Search complete',
  peer_review_started: 'Peer review',
  model_b_calibrated: 'Dixon-Coles calibrated',
  form_index_computed: 'Form index applied',
  model_c_trained: 'XGBoost trained',
  model_c_skipped: 'XGBoost skipped',
  predictions_computed: 'Computing predictions',
  synthesis_started: 'Synthesising the answer',
  report_built: 'Report assembled',
  reload_notice: 'Reconnecting',
  stage_error: 'Something went wrong',
};

// Per-event leading icons (default is a bullet, handled in the render).
const ICON = {
  model_b_calibrated: BarChart3,
  form_index_computed: TrendingUp,
  model_c_trained: CheckCircle2,
  model_c_skipped: AlertCircle,
};
// Events whose icon should render amber rather than muted.
const ICON_AMBER = new Set(['model_c_skipped']);

function titleFor(item) {
  const e = item.event;
  if (e === 'model_querying') {
    const m = (item.detail || '').replace(/^Querying\s*/, '').replace(/\.\.\.$/, '');
    return `Consulting ${m}`;
  }
  if (e === 'model_responded') {
    const m = (item.detail || '').split(' · ')[0];
    return `${m} responded`;
  }
  return TITLE[e] || item.detail || 'Activity';
}

function domainOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export default function ActivityPanel({ log, open, onClose }) {
  const [tab, setTab] = useState('timeline');
  const timelineRef = useRef(null);

  useEffect(() => {
    if (open && tab === 'timeline' && timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [log, tab, open]);

  const sources = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const item of log) {
      if (item.event === 'search_complete') {
        for (const link of item.links || []) {
          if (link.url && !seen.has(link.url)) {
            seen.add(link.url);
            out.push(link);
          }
        }
      }
    }
    return out;
  }, [log]);

  const tabPill = (id, label) => (
    <button
      onClick={() => setTab(id)}
      className={`px-2.5 py-1 rounded-full text-xs transition ${
        tab === id
          ? 'bg-[var(--user-bubble)] text-[var(--text)]'
          : 'text-[var(--muted)] hover:text-[var(--text)]'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div
      className={`shrink-0 h-screen overflow-hidden transition-[width] duration-300 ease-out ${
        open ? 'w-[360px]' : 'w-0'
      }`}
    >
     <div className="w-[360px] h-screen flex flex-col bg-[oklch(0.10_0_0)] border-l border-[var(--border)]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <span className="text-sm font-semibold text-[var(--text)]">Activity</span>
        <div className="flex items-center gap-1 ml-auto">
          {tabPill('timeline', 'Research Activity')}
          {tabPill('sources', 'Sources')}
        </div>
        <button
          onClick={onClose}
          aria-label="Close activity panel"
          className="ml-1 w-6 h-6 flex items-center justify-center rounded text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--user-bubble)]"
        >
          <X size={16} strokeWidth={1.5} />
        </button>
      </div>

      {/* Research Activity tab */}
      {tab === 'timeline' && (
        <div ref={timelineRef} className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
          {log.length === 0 ? (
            <div className="text-[var(--faint)] text-sm">Waiting for activity…</div>
          ) : (
            log.map((item, i) => {
              const isError = item.event === 'stage_error';
              const description = item.reasoning || item.detail;
              const Icon = ICON[item.event];
              return (
                <div key={i} className="flex gap-2 pl-3 border-l-2 border-[oklch(0.28_0_0)]">
                  {Icon ? (
                    <Icon size={14} strokeWidth={1.5} className={`mt-0.5 shrink-0 ${ICON_AMBER.has(item.event) ? 'text-amber-400' : 'text-[var(--muted)]'}`} />
                  ) : (
                    <span className={`leading-5 ${isError ? 'text-[var(--danger)]' : 'text-[var(--muted)]'}`}>•</span>
                  )}
                  <div className="flex-1">
                    <div className={`text-[13px] font-semibold ${isError ? 'text-[var(--danger)]' : 'text-white'}`}>
                      {titleFor(item)}
                    </div>
                    {description && (
                      <div className={`text-[13px] mt-0.5 leading-relaxed ${isError ? 'text-[var(--danger)]' : 'text-[oklch(0.55_0_0)]'}`}>
                        {description}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Sources tab (unchanged list style) */}
      {tab === 'sources' && (
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {sources.length === 0 ? (
            <div className="text-[var(--faint)] text-sm">No web sources — text-only mode</div>
          ) : (
            sources.map((s, i) => (
              <div key={i} className="py-2.5 border-b border-[var(--border)] last:border-b-0">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[13px] text-[oklch(0.75_0_0)] no-underline hover:text-white hover:underline"
                >
                  {s.title || s.url}
                </a>
                <div className="text-[11px] text-[var(--faint)] mt-0.5">{domainOf(s.url)}</div>
              </div>
            ))
          )}
        </div>
      )}
     </div>
    </div>
  );
}
