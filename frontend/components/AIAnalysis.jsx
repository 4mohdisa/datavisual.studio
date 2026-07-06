import ReactMarkdown from 'react-markdown';

// Section 3 — the chairman's narrative only. Predictions now live in Sections 1
// and 2, so no prediction table here — just the explanation, confidence and sources.
const CONFIDENCE_LABELS = { high: 'High', medium: 'Medium', low: 'Low' };
const CONFIDENCE_CLASS = {
  high: 'bg-[rgba(40,167,69,0.2)] text-[#5cb85c] border border-[rgba(40,167,69,0.4)]',
  medium: 'bg-[rgba(255,193,7,0.15)] text-[#f0ad4e] border border-[rgba(255,193,7,0.3)]',
  low: 'bg-[rgba(220,53,69,0.15)] text-[#d9534f] border border-[rgba(220,53,69,0.3)]',
};

export default function AIAnalysis({ chairmanSynthesis }) {
  if (!chairmanSynthesis) return null;
  const { content, confidence, caveats = [], sources = [], model } = chairmanSynthesis;
  if (!content && sources.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5 flex-wrap">
        {model && (
          <span className="text-xs text-[var(--muted)] italic">Synthesised by {model.split('/').pop()}</span>
        )}
        {confidence && (
          <span className={`inline-block px-2.5 py-0.5 rounded-xl text-[11px] font-bold uppercase tracking-wide ${CONFIDENCE_CLASS[confidence] || ''}`}>
            {CONFIDENCE_LABELS[confidence] || confidence} confidence
          </span>
        )}
      </div>

      {content && (
        <div className="markdown-content text-[oklch(0.85_0_0)] leading-[1.75]">
          <ReactMarkdown>{content}</ReactMarkdown>
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
