import { useState, useMemo, useEffect, useRef } from 'react';

// 6.4 — Cmd/Ctrl+K command palette: fuzzy-ish search over conversation titles.
export default function CommandPalette({ conversations, onSelect, onClose }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? conversations.filter((c) => (c.title || '').toLowerCase().includes(q))
      : conversations;
    return list.slice(0, 8);
  }, [conversations, query]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50" onClick={onClose}>
      <div
        className="w-[520px] max-w-[90vw] bg-[var(--surface-input)] border border-[var(--border-2)] rounded-xl shadow-[0_8px_40px_rgba(0,0,0,0.5)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search conversations…"
          className="w-full bg-transparent px-4 py-3 text-[15px] text-[var(--text)] placeholder:text-[var(--faint)] outline-none border-b border-[var(--border)]"
        />
        <div className="max-h-[320px] overflow-y-auto py-1">
          {results.length === 0 ? (
            <div className="px-4 py-3 text-[13px] text-[var(--faint)]">No matches</div>
          ) : (
            results.map((c) => (
              <button
                key={c.id}
                onClick={() => { onSelect(c.id); onClose(); }}
                className="w-full text-left px-4 py-2 text-[13px] text-[var(--text)] hover:bg-[var(--active)] truncate"
              >
                {c.title || 'New conversation'}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
