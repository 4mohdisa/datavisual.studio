import { useState } from 'react';

export default function ReportSection({ title, children, defaultOpen = true, badge, subtitle }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-[var(--border)]">
      <button
        className="w-full py-3.5 bg-transparent border-0 cursor-pointer text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center justify-between">
          <span className="text-[var(--text)] text-[16px] font-semibold">
            {title}
            {badge != null && <span className="ml-2 text-[12px] font-normal text-[var(--muted)]">{badge}</span>}
          </span>
          <span
            className={`text-xl text-[var(--muted)] inline-block transition-transform ${
              open ? 'rotate-[270deg]' : 'rotate-90'
            }`}
          >
            ›
          </span>
        </div>
        {/* Preview subtitle shown only when collapsed (1.3). */}
        {subtitle && !open && (
          <div className="text-[12px] text-[var(--faint)] mt-1 pr-6">{subtitle}</div>
        )}
      </button>
      {open && <div className="pb-4 pt-1">{children}</div>}
    </div>
  );
}
