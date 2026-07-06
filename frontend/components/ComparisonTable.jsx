import { useState } from 'react';

export default function ComparisonTable({ headers, rows, title }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');

  if (!rows || rows.length === 0) return null;

  const derivedHeaders = headers || Object.keys(rows[0]);

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  const sorted = sortCol
    ? [...rows].sort((a, b) => {
        const av = a[sortCol] ?? '';
        const bv = b[sortCol] ?? '';
        const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
        return sortDir === 'asc' ? cmp : -cmp;
      })
    : rows;

  return (
    <div className="my-4">
      {title && (
        <div className="text-[13px] font-semibold text-[var(--muted)] uppercase tracking-wide mb-2">
          {title}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr>
              {derivedHeaders.map((h) => (
                <th
                  key={h}
                  onClick={() => handleSort(h)}
                  className="bg-[var(--user-bubble)] text-[oklch(0.80_0_0)] px-3 py-2 text-left border-b border-[var(--border-2)] whitespace-nowrap cursor-pointer select-none hover:bg-[var(--border-2)] hover:text-white"
                >
                  {h}
                  {sortCol === h && (
                    <span className="text-[var(--accent)]">{sortDir === 'asc' ? ' ↑' : ' ↓'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={i} className="hover:bg-[var(--active)]">
                {derivedHeaders.map((h) => (
                  <td key={h} className="px-3 py-2 border-b border-[var(--border)] text-[oklch(0.85_0_0)] align-top">
                    {row[h] ?? '–'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
