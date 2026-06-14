import { AlertCircle, RotateCcw } from 'lucide-react';

export default function ErrorState({ title, message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[50vh] px-4">
      <AlertCircle size={32} strokeWidth={1.5} className="text-amber-400 mb-3" />
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      {message && <p className="text-sm text-[var(--muted)] max-w-[420px] leading-relaxed">{message}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium bg-white text-black hover:bg-[oklch(0.88_0_0)] transition"
        >
          <RotateCcw size={16} strokeWidth={1.5} />
          Try again
        </button>
      )}
    </div>
  );
}
