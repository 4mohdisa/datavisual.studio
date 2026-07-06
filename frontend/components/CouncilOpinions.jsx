import { useState } from 'react';
import { Check, Circle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import ComparisonTable from './ComparisonTable';

export default function CouncilOpinions({ councilOpinions }) {
  const [activeTab, setActiveTab] = useState(0);
  const [visibleModels, setVisibleModels] = useState(null); // null = all visible

  if (!councilOpinions) return null;

  const { models = [], responses = {}, agreement, model_comparison_table, aggregate_rankings } = councilOpinions;

  const shown = visibleModels === null ? models : models.filter((m) => visibleModels.has(m));

  const toggleModel = (model) => {
    setVisibleModels((prev) => {
      const next = new Set(prev === null ? models : prev);
      if (next.has(model)) next.delete(model);
      else next.add(model);
      return next.size === models.length ? null : next;
    });
    setActiveTab(0);
  };

  const modelLabel = (m) => m.split('/').pop();

  return (
    <div className="flex flex-col gap-4">
      {/* Model toggles */}
      <div className="flex flex-wrap gap-2">
        {models.map((m) => {
          const active = visibleModels === null || visibleModels.has(m);
          return (
            <button
              key={m}
              onClick={() => toggleModel(m)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-2xl border text-xs cursor-pointer transition ${
                active
                  ? 'border-[var(--accent)] text-[var(--accent)] bg-[rgba(74,144,226,0.1)]'
                  : 'border-[var(--border-3)] text-[var(--muted)] opacity-50'
              }`}
            >
              {active ? <Check size={14} strokeWidth={1.5} /> : <Circle size={14} strokeWidth={1.5} />}
              {modelLabel(m)}
            </button>
          );
        })}
      </div>

      {/* Aggregate ranking */}
      {aggregate_rankings && aggregate_rankings.length > 0 && (
        <div className="bg-[var(--raised)] border border-[var(--border)] rounded-md px-3.5 py-3">
          <div className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wide mb-2">
            Peer ranking (lower = better)
          </div>
          {aggregate_rankings.map((r, i) => (
            <div key={r.model} className="flex items-center gap-2.5 py-1 text-[13px]">
              <span className="text-[var(--faint)] w-6">#{i + 1}</span>
              <span className="text-[oklch(0.85_0_0)] flex-1">{modelLabel(r.model)}</span>
              <span className="text-[var(--muted)] text-xs">avg {r.average_rank}</span>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      {shown.length > 0 && (
        <>
          <div className="flex gap-1 border-b border-[var(--border)] flex-wrap">
            {shown.map((m, i) => (
              <button
                key={m}
                onClick={() => setActiveTab(i)}
                className={`px-3.5 py-1.5 -mb-px border-b-2 text-[13px] cursor-pointer transition ${
                  activeTab === i
                    ? 'text-[var(--accent)] border-[var(--accent)]'
                    : 'text-[var(--muted)] border-transparent hover:text-[oklch(0.80_0_0)]'
                }`}
              >
                {modelLabel(m)}
              </button>
            ))}
          </div>

          <div className="py-3 text-[oklch(0.82_0_0)] leading-relaxed">
            {shown[activeTab] && (() => {
              const resp = responses[shown[activeTab]] || {};
              return (
                <div className="markdown-content">
                  <ReactMarkdown>{resp.stage1 || ''}</ReactMarkdown>
                </div>
              );
            })()}
          </div>
        </>
      )}

      {/* Agreement summary */}
      {agreement && (
        <div className="text-[13px] text-[var(--muted)] italic px-3 py-2 bg-[var(--raised)] border-l-[3px] border-[var(--accent)] rounded-r">
          {agreement}
        </div>
      )}

      {/* Model vs model table */}
      {model_comparison_table && model_comparison_table.length > 0 && (
        <ComparisonTable rows={model_comparison_table} title="Model vs Model" />
      )}
    </div>
  );
}
