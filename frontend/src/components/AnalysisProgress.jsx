// Vertical timeline: a line down the left, a circle node per stage, label on the
// right. Active node pulses; completed nodes are filled (1.4).

function Node({ status, label, last }) {
  if (!status || status === 'skipped') return null;
  const isDone = status === 'done';
  const isActive = status === 'active';

  const circle = isDone
    ? 'bg-[#4ad07f] border-[#4ad07f]'
    : isActive
    ? 'bg-[var(--accent)] border-[var(--accent)] animate-pulse'
    : 'bg-transparent border-[var(--faint)]';

  const text = isActive
    ? 'text-[var(--text)]'
    : isDone
    ? 'text-[var(--muted)]'
    : 'text-[var(--faint)]';

  return (
    <div className="flex gap-3">
      {/* left rail: connector line + node */}
      <div className="relative flex flex-col items-center">
        <span className={`mt-0.5 w-3 h-3 rounded-full border-2 shrink-0 ${circle}`} />
        {!last && <span className="w-px flex-1 bg-[var(--border-2)] my-1" />}
      </div>
      <div className={`text-[14px] pb-3 ${text} ${isActive ? 'animate-[ap-fade-in_0.35s_ease]' : ''}`}>
        {label}
      </div>
    </div>
  );
}

export default function AnalysisProgress({ progress }) {
  if (!progress) return null;

  if (progress.followup) {
    return (
      <div className="flex flex-col max-w-[460px]">
        <Node status={progress.followup} label="Consulting the chairman…" last />
      </div>
    );
  }

  const { analysis, research, stage1, stage2, stage3, report } = progress;

  let council = 'pending';
  if (stage3 === 'done') council = 'done';
  else if ([stage1, stage2, stage3].includes('active') || stage1 === 'done' || stage2 === 'done') {
    council = 'active';
  }

  // Build the node list, dropping skipped stages so `last` lands on the real tail.
  const nodes = [
    { status: analysis, label: 'Analysing dataset' },
    { status: research, label: 'Searching the web' },
    { status: council, label: 'Consulting the council' },
    { status: stage1, label: 'Stage 1 — Individual responses' },
    { status: stage2, label: 'Stage 2 — Peer review' },
    { status: stage3, label: 'Stage 3 — Chairman synthesis' },
    { status: report, label: 'Building report' },
  ].filter((n) => n.status && n.status !== 'skipped');

  return (
    <div className="flex flex-col max-w-[460px]">
      {nodes.map((n, i) => (
        <Node key={n.label} status={n.status} label={n.label} last={i === nodes.length - 1} />
      ))}
    </div>
  );
}
