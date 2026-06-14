import { useEffect } from 'react';

export default function ConfirmDialog({ title, body, confirmLabel = 'Confirm', onConfirm, onCancel }) {
  // Close on Escape.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onCancel?.();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="w-[400px] max-w-[90vw] bg-[var(--surface-input)] border border-[var(--border-2)] rounded-xl shadow-[0_8px_40px_rgba(0,0,0,0.5)] p-5"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h3 className="text-base font-semibold text-[var(--text)] mb-2">{title}</h3>
        <p className="text-sm text-[var(--muted)] leading-relaxed mb-5">{body}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-md text-sm text-[var(--text)] bg-[var(--user-bubble)] hover:bg-[var(--active)] transition"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-md text-sm font-medium text-white bg-[var(--danger)] hover:brightness-110 transition"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
