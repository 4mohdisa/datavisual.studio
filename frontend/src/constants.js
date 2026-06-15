// Shared frontend constants (7.1). Centralises values that were repeated across
// components. (A full migration of every literal is ongoing; the most-reused
// values live here.)

// Default prediction source weights (dataset / internet / council).
export const DEFAULT_WEIGHTS = { dataset: 40, internet: 35, council: 25 };

// Model-agreement thresholds and their colours.
export const AGREEMENT = {
  high: 0.85,
  medium: 0.65,
  colors: { green: '#4ade80', amber: '#fbbf24', red: '#f87171' },
};

// Per-model accent colours used across the prediction charts.
export const MODEL_COLORS = { a: '#4a90e2', b: '#9b59e0', c: '#5cb85c', ensemble: '#ffffff' };

// Source-quality badge glyphs.
export const SOURCE_QUALITY = {
  authoritative: { dot: '🟢', label: 'Authoritative' },
  standard: { dot: '🟡', label: 'Standard' },
  unknown: { dot: '🔴', label: 'Unknown' },
};
