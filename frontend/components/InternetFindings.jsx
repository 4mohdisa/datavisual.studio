import ReactMarkdown from 'react-markdown';
import ComparisonTable from './ComparisonTable';

// Source quality badge (3.2).
const QUALITY = {
  authoritative: { dot: '🟢', label: 'Authoritative' },
  standard: { dot: '🟡', label: 'Standard' },
  unknown: { dot: '🔴', label: 'Unknown' },
};

function ResearchSummary({ summary }) {
  if (!summary || !summary.n_searches) return null;
  const parts = [
    `${summary.n_searches} searches`,
    `${summary.n_sources} sources`,
    summary.n_live_scores ? `${summary.n_live_scores} live scores detected` : null,
    summary.n_probability_values ? `Probability values found: ${summary.n_probability_values}` : null,
    summary.as_of ? `As of ${summary.as_of}` : null,
  ].filter(Boolean);
  return (
    <div className="rounded-md border border-[var(--border-2)] bg-[var(--raised)] px-3 py-2 text-[12px] text-[var(--muted)]">
      {parts.join(' · ')}
    </div>
  );
}

function LiveResults({ scores }) {
  if (!scores || scores.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide">Live Results</div>
      <div className="flex flex-wrap gap-2">
        {scores.map((s, i) => (
          <span key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--active)] border border-[var(--border-2)] text-[13px] text-[oklch(0.88_0_0)]">
            {s.home_team} <span className="text-[var(--muted)]">🆚</span> {s.away_team}
            <span className="font-semibold tabular-nums">— {s.home_goals}:{s.away_goals}</span>
            <span className="text-green-400">✅</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function InternetFindings({ internetResearch }) {
  if (!internetResearch) return null;

  const { findings, sources, internet_vs_council_table, available, live_scores, summary } = internetResearch;
  const isAvailable = available !== undefined ? available : !!findings;

  if (!isAvailable) {
    return (
      <div className="text-[var(--muted)] italic text-sm py-2">
        Internet research unavailable for this query.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ResearchSummary summary={summary} />
      <LiveResults scores={live_scores} />

      {findings && (
        <div className="markdown-content text-[oklch(0.82_0_0)] leading-relaxed">
          <ReactMarkdown>{findings}</ReactMarkdown>
        </div>
      )}

      {sources && sources.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-2">
            Sources
          </div>
          <ul className="list-none p-0 m-0 flex flex-col gap-1">
            {sources.map((s, i) => {
              const q = QUALITY[s.quality] || QUALITY.unknown;
              return (
                <li key={i} className="text-[13px] flex items-center gap-1.5">
                  <span title={q.label} className="text-[10px]">{q.dot}</span>
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] no-underline hover:underline">
                      {s.title || s.url}
                    </a>
                  ) : (
                    <span>{s.title}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {internet_vs_council_table && internet_vs_council_table.length > 0 && (
        <ComparisonTable rows={internet_vs_council_table} title="Internet vs Council" />
      )}
    </div>
  );
}
