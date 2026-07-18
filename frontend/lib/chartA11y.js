// Deterministic text alternatives for Plotly charts (Phase 4d). Charts are
// invisible to screen readers; a data-viz product with unreadable charts is a
// real gap. These derive an aria-label summary AND a data table straight from
// the plotly spec — NOT the LLM — so every chart is readable and every number
// is the one actually plotted.
//
// Plotly encodes numeric columns as binary typed arrays ({dtype, bdata:base64})
// rather than plain JS arrays, so we decode those before summarising.

const DTYPE = {
  f8: ['getFloat64', 8], f4: ['getFloat32', 4],
  i4: ['getInt32', 4], i2: ['getInt16', 2], i1: ['getInt8', 1],
  u4: ['getUint32', 4], u2: ['getUint16', 2], u1: ['getUint8', 1],
};

function decodeBinary(v) {
  const spec = DTYPE[v.dtype];
  if (!spec || typeof atob !== 'function') return [];
  const [getter, size] = spec;
  let bin;
  try { bin = atob(v.bdata); } catch { return []; }
  const buf = new ArrayBuffer(bin.length);
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const dv = new DataView(buf);
  const out = [];
  for (let i = 0; i + size <= bin.length; i += size) out.push(dv[getter](i, true)); // little-endian
  return out;
}

// A plotly axis value: a plain array, a binary typed array, or nothing.
function toValues(v) {
  if (Array.isArray(v)) return v;
  if (v && typeof v === 'object' && v.bdata && v.dtype) return decodeBinary(v);
  return [];
}
function toNums(v) {
  return toValues(v).map(Number).filter((n) => !Number.isNaN(n));
}

const fmt = (v) => {
  if (typeof v !== 'number' || Number.isNaN(v)) return String(v ?? '');
  return Number.isInteger(v)
    ? v.toLocaleString()
    : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
};

const KIND = { scatter: 'line', scatterpolar: 'radar', bar: 'bar', pie: 'pie',
  histogram: 'histogram', box: 'box', heatmap: 'heatmap', treemap: 'treemap' };

function chartKind(data) {
  const t = data[0]?.type || 'scatter';
  const mode = data[0]?.mode || '';
  if (t === 'scatter' && mode.includes('markers') && !mode.includes('lines')) return 'scatter';
  return KIND[t] || t;
}

// A one-sentence summary suitable for role="img" aria-label.
export function chartSummary(title, data) {
  data = Array.isArray(data) ? data : [];
  if (!data.length) return `Chart${title ? `: ${title}` : ''}. No data.`;
  const head = `${chartKind(data)} chart${title ? `: ${title}` : ''}.`;
  const series = data.slice(0, 6).map((tr, i) => {
    const name = tr.name || tr.type || `series ${i + 1}`;
    if (tr.type === 'pie') {
      const labels = toValues(tr.labels);
      const values = toNums(tr.values);
      const pairs = labels.map((l, j) => [l, values[j] || 0]).sort((a, b) => b[1] - a[1]);
      return pairs.length ? `largest slice ${pairs[0][0]} (${fmt(pairs[0][1])})` : name;
    }
    // Prefer y, fall back to x (histograms/bars may carry values on either axis).
    const ys = toNums(tr.y).length ? toNums(tr.y) : toNums(tr.x);
    if (!ys.length) return name;
    const first = ys[0], last = ys[ys.length - 1];
    const min = Math.min(...ys), max = Math.max(...ys);
    if (ys.length > 1 && first !== last) return `${name} from ${fmt(first)} to ${fmt(last)} (min ${fmt(min)}, max ${fmt(max)})`;
    return `${name}: ${fmt(max)}`;
  });
  return [head, series.join('; ') + '.'].join(' ');
}

// The same data as a { columns, rows } table — the text alternative rendered by
// the "View as table" toggle.
export function chartToTable(data) {
  data = Array.isArray(data) ? data : [];
  const pie = data.find((t) => t.type === 'pie');
  if (pie) {
    const labels = toValues(pie.labels);
    const values = toValues(pie.values);
    return { columns: ['Label', 'Value'],
      rows: labels.map((l, i) => ({ Label: l, Value: values[i] })) };
  }
  const xs = toValues(data[0]?.x);
  const names = data.map((t, i) => t.name || `Series ${i + 1}`);
  const ys = data.map((t) => toValues(t.y));
  const columns = ['', ...names];
  const rows = xs.map((x, i) => {
    const row = { '': x };
    names.forEach((n, j) => { row[n] = ys[j][i]; });
    return row;
  });
  return { columns, rows };
}
