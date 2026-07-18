// Mirror of the backend `classify_intent` (backend/dashboard.py) so the
// assistant's busy status describes what the server will ACTUALLY do. The
// server owns the final decision — for the genuinely ambiguous residual it
// makes one LLM call the client can't replicate, so those render as a neutral
// "Working…" rather than a wrong guess. Keep the keyword lists in sync with
// the server; a spinner that names the wrong action is worse than none.

const EDIT_NOUNS = ['chart', 'metric', 'pie', 'bar', 'graph', 'widget',
  'table', 'comparison', 'donut', 'histogram', 'scatter', 'heatmap', 'line'];
const STARTS_EDIT = /^(add|remove|delete|rename|move|pin|make|create|put|drop|insert|update|set|build|change)\b/;
const STARTS_Q = /^(what|which|how|why|when|who|is|are|does|do|list|tell|show me|give me)\b/;
const Q_WORDS = /\b(average|highest|lowest|top|total|compare|biggest|smallest|most|least|mean|median|sum)\b/;
const RESEARCH = /\b(research|search the web|online|latest news)\b/;

// 'question' | 'edit' | 'both' | 'research' | 'ambiguous'
export function classifyIntent(message) {
  const m = (message || '').toLowerCase().trim();
  if (!m) return 'ambiguous';
  if (RESEARCH.test(m)) return 'research';
  const hasEdit = STARTS_EDIT.test(m) || EDIT_NOUNS.some((n) => m.includes(n));
  const hasQ = m.includes('?') || STARTS_Q.test(m) || Q_WORDS.test(m);
  if (hasEdit && hasQ) return 'both';
  if (hasEdit) return 'edit';
  if (hasQ) return 'question';
  return 'ambiguous';
}

const LABELS = {
  research: 'Searching the web…',
  both: 'Answering and updating…',
  edit: 'Updating the dashboard…',
  question: 'Reading your data…',
  ambiguous: 'Working…',
};

export function busyLabel(message) {
  return LABELS[classifyIntent(message)];
}
