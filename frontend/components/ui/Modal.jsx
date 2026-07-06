'use client';

import { useEffect } from 'react';
import { X } from 'lucide-react';

// Modal primitive: dark overlay, centred panel, Escape/overlay-click to close.
// `title` renders a header row with a close button; omit it for bare dialogs.
export default function Modal({ title, onClose, width = 'w-[480px]', children }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className={`${width} max-w-[92vw] max-h-[85vh] overflow-y-auto bg-[var(--surface-input)] border border-[var(--border-2)] rounded-xl shadow-[0_8px_40px_rgba(0,0,0,0.5)] p-6`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {title && (
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-[var(--text)] m-0">{title}</h3>
            <button
              onClick={onClose}
              className="p-1 rounded text-[var(--muted)] hover:text-[var(--text)]"
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
