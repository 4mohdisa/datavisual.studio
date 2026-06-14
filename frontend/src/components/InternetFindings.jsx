import ReactMarkdown from 'react-markdown';
import ComparisonTable from './ComparisonTable';

export default function InternetFindings({ internetResearch }) {
  if (!internetResearch) return null;

  const { findings, sources, internet_vs_council_table, available } = internetResearch;

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
            {sources.map((s, i) => (
              <li key={i} className="text-[13px]">
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

      {internet_vs_council_table && internet_vs_council_table.length > 0 && (
        <ComparisonTable rows={internet_vs_council_table} title="Internet vs Council" />
      )}
    </div>
  );
}
