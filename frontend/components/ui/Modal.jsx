'use client';

import { useId } from 'react';
import { X } from 'lucide-react';
import { useFocusTrap } from './useFocusTrap';

// Modal primitive: dark overlay, centred panel, Escape/overlay-click to close.
// Focus is trapped while open and restored to the trigger on close (Phase 1c).
// `title` renders a header row + close button and labels the dialog for AT;
// omit it for bare dialogs.
export default function Modal({ title, onClose, width = 'w-[480px]', children }) {
  const titleId = useId();
  const ref = useFocusTrap({ active: true, onEscape: onClose });

  return (
    <div className="fixed inset-0 z-[var(--z-modal,50)] flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        ref={ref}
        className={`${width} max-w-[92vw] max-h-[85vh] overflow-y-auto bg-[var(--surface-input)] border border-[var(--border-2)] rounded-xl shadow-[0_8px_40px_rgba(0,0,0,0.5)] p-6 outline-none`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
      >
        {title && (
          <div className="flex items-center justify-between mb-4">
            <h3 id={titleId} className="text-base font-semibold text-[var(--text)] m-0">{title}</h3>
            <button
              onClick={onClose}
              className="p-1 rounded text-[var(--muted)] hover:text-[var(--text)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)]"
              aria-label={`Close ${title.toLowerCase()}`}
            >
              <X size={18} strokeWidth={1.5} />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
