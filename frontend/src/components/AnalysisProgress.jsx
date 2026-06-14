import { CheckCircle2, Loader2, Circle } from 'lucide-react';

function Icon({ status }) {
  if (status === 'done') return <CheckCircle2 size={14} strokeWidth={1.5} className="shrink-0 text-[#4ad07f]" />;
  if (status === 'active') return <Loader2 size={16} strokeWidth={1.5} className="shrink-0 text-[var(--accent)] animate-spin" />;
  return <Circle size={16} strokeWidth={1.5} className="shrink-0 text-[var(--faint)]" />;
}

function Line({ status, label, indent }) {
  if (!status || status === 'skipped') return null;
  const color =
    status === 'active'
      ? 'text-[var(--text)] animate-[ap-fade-in_0.35s_ease]'
      : status === 'done'
      ? 'text-[var(--muted)]'
      : 'text-[var(--faint)]';
  return (
    <div className={`flex items-center gap-2.5 transition-colors ${color} ${indent ? 'pl-[26px] text-[13px]' : 'text-sm'}`}>
      <Icon status={status} />
      <span>{label}</span>
    </div>
  );
}

export default function AnalysisProgress({ progress }) {
  if (!progress) return null;

  if (progress.followup) {
    return (
      <div className="flex flex-col gap-2.5 max-w-[460px]">
        <Line status={progress.followup} label="Consulting the chairman…" />
      </div>
    );
  }

  const { analysis, research, stage1, stage2, stage3, report } = progress;

  let council = 'pending';
  if (stage3 === 'done') council = 'done';
  else if ([stage1, stage2, stage3].includes('active') || stage1 === 'done' || stage2 === 'done') {
    council = 'active';
  }

  return (
    <div className="flex flex-col gap-2.5 max-w-[460px]">
      <Line status={analysis} label="Analysing dataset…" />
      <Line status={research} label="Searching the web…" />
      <Line status={council} label="Consulting the council…" />
      <Line status={stage1} label="Stage 1 — Individual responses" indent />
      <Line status={stage2} label="Stage 2 — Peer review" indent />
      <Line status={stage3} label="Stage 3 — Chairman synthesis" indent />
      <Line status={report} label="Building report…" />
    </div>
  );
}
