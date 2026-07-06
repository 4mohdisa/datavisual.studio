import ReactMarkdown from 'react-markdown';

export default function Stage3({ finalResponse }) {
  if (!finalResponse) return null;

  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs text-[var(--muted)] italic">
        Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
      </div>
      <div className="markdown-content text-[oklch(0.85_0_0)] leading-relaxed">
        <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
      </div>
    </div>
  );
}
