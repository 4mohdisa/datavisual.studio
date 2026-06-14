import { useState, useEffect } from 'react';
import { api } from '../api';

export default function ExportButton({ conversationId }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [format, setFormat] = useState('pdf'); // 'pdf' | 'html'

  useEffect(() => {
    let active = true;
    api.getExportFormat().then((f) => { if (active) setFormat(f); });
    return () => { active = false; };
  }, []);

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.exportReport(conversationId);
    } catch (e) {
      setError(e?.message || 'Report generation failed. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const label = format === 'html' ? 'Download HTML Report' : 'Download PDF Report';

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        onClick={handleExport}
        disabled={loading}
        className="px-4 py-2 rounded-[0.2rem] text-sm font-medium cursor-pointer transition bg-[var(--new-chat)] text-[var(--background)] hover:bg-[var(--new-chat-hover)] disabled:opacity-60 disabled:cursor-default"
      >
        {loading ? 'Generating…' : label}
      </button>
      {format === 'html' && (
        <div className="text-xs text-[var(--muted)]">
          PDF tooling unavailable on the server — exporting a self-contained HTML report instead.
        </div>
      )}
      {error && <div className="text-[13px] text-[var(--danger)] whitespace-pre-wrap">{error}</div>}
    </div>
  );
}
