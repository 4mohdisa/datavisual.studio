import { useState } from 'react';

export default function ReportSection({ title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-[var(--border)]">
      <button
        className="w-full flex items-center justify-between py-3.5 bg-transparent border-0 cursor-pointer text-[var(--text)] text-[15px] font-semibold text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <span>{title}</span>
        <span
          className={`text-xl text-[var(--muted)] inline-block transition-transform ${
            open ? 'rotate-[270deg]' : 'rotate-90'
          }`}
        >
          ›
        </span>
      </button>
      {open && <div className="pb-4 pt-1">{children}</div>}
    </div>
  );
}
