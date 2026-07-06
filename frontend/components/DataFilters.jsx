import { useState } from 'react';
import { api } from '../lib/api';

const INPUT_CLASS =
  'bg-[var(--background)] border border-[var(--border-3)] rounded-[5px] text-[var(--text)] px-2.5 py-1.5 text-[13px] outline-none focus:border-[var(--accent)]';

export default function DataFilters({ availableFilters, conversationId, onFiltersApplied }) {
  const [dateRange, setDateRange] = useState(['', '']);
  const [categories, setCategories] = useState({});
  const [numericRanges, setNumericRanges] = useState({});
  const [loading, setLoading] = useState(false);

  if (!availableFilters || Object.keys(availableFilters).length === 0) return null;

  const hasDateFilter = !!availableFilters.date_range;
  const catCols = availableFilters.categories || [];
  const numCols = availableFilters.numeric_ranges || [];

  const handleApply = async () => {
    setLoading(true);
    try {
      const filters = {};
      if (hasDateFilter && (dateRange[0] || dateRange[1])) filters.date_range = dateRange;
      if (Object.keys(categories).length > 0) filters.categories = categories;
      if (Object.keys(numericRanges).length > 0) filters.numeric_ranges = numericRanges;
      const result = await api.reanalyse(conversationId, filters);
      onFiltersApplied(result);
    } finally {
      setLoading(false);
    }
  };

  const label = (text) => (
    <label className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide">{text}</label>
  );

  return (
    <div className="flex flex-col gap-3.5">
      {hasDateFilter && (
        <div className="flex flex-col gap-1.5">
          {label(`Date range (${availableFilters.date_range.column})`)}
          <div className="flex items-center gap-2">
            <input type="date" value={dateRange[0]} onChange={(e) => setDateRange([e.target.value, dateRange[1]])} className={INPUT_CLASS} />
            <span className="text-[var(--faint)] text-[13px]">→</span>
            <input type="date" value={dateRange[1]} onChange={(e) => setDateRange([dateRange[0], e.target.value])} className={INPUT_CLASS} />
          </div>
        </div>
      )}

      {catCols.map((col) => (
        <div key={col} className="flex flex-col gap-1.5">
          {label(col)}
          <input
            type="text"
            placeholder="Filter values (comma-separated)"
            className={INPUT_CLASS}
            onChange={(e) => {
              const vals = e.target.value.split(',').map((v) => v.trim()).filter(Boolean);
              setCategories((prev) => ({ ...prev, [col]: vals }));
            }}
          />
        </div>
      ))}

      {numCols.map((col) => (
        <div key={col} className="flex flex-col gap-1.5">
          {label(`${col} range`)}
          <div className="flex items-center gap-2">
            <input
              type="number"
              placeholder="Min"
              className={`${INPUT_CLASS} w-[100px]`}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setNumericRanges((prev) => {
                  const cur = prev[col] || [null, null];
                  return { ...prev, [col]: [isNaN(val) ? null : val, cur[1]] };
                });
              }}
            />
            <span className="text-[var(--faint)] text-[13px]">–</span>
            <input
              type="number"
              placeholder="Max"
              className={`${INPUT_CLASS} w-[100px]`}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setNumericRanges((prev) => {
                  const cur = prev[col] || [null, null];
                  return { ...prev, [col]: [cur[0], isNaN(val) ? null : val] };
                });
              }}
            />
          </div>
        </div>
      ))}

      <button
        onClick={handleApply}
        disabled={loading}
        className="self-start px-5 py-1.5 bg-[var(--accent)] text-white border-0 rounded-[5px] text-[13px] font-semibold cursor-pointer transition hover:bg-[#357abd] disabled:opacity-60 disabled:cursor-default"
      >
        {loading ? 'Applying…' : 'Apply filters'}
      </button>
    </div>
  );
}
