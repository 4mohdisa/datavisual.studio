import { describe, it, expect } from 'vitest';
import { chartSummary, chartToTable } from './chartA11y';

const LINE = [
  { type: 'scatter', mode: 'lines+markers', name: 'Enterprise', x: ['Jan', 'Feb', 'Jun'], y: [41200, 43130, 52761] },
  { type: 'scatter', mode: 'lines+markers', name: 'Pro', x: ['Jan', 'Feb', 'Jun'], y: [21759, 23367, 27888] },
];
const PIE = [{ type: 'pie', labels: ['Starter', 'Pro', 'Enterprise'], values: [483, 207, 41] }];

describe('chartSummary', () => {
  it('summarises a multi-series line chart from real numbers', () => {
    const s = chartSummary('MRR over time by plan', LINE);
    expect(s).toContain('line chart: MRR over time by plan');
    expect(s).toContain('Enterprise from 41,200 to 52,761');
    expect(s).toContain('min 41,200, max 52,761');
  });

  it('names the largest slice of a pie', () => {
    expect(chartSummary('Customers by plan', PIE)).toContain('largest slice Starter (483)');
  });

  it('degrades safely with no data', () => {
    expect(chartSummary('Empty', [])).toBe('Chart: Empty. No data.');
  });

  it('never throws on traces without a y array (histogram, malformed)', () => {
    const hist = [{ type: 'histogram', x: [10, 20, 20, 30] }];
    expect(() => chartSummary('Distribution', hist)).not.toThrow();
    expect(chartSummary('Distribution', hist)).toContain('histogram chart');
    // y as a non-array must not crash
    expect(() => chartSummary('Weird', [{ type: 'bar', name: 'x', y: 5 }])).not.toThrow();
  });

  it('decodes Plotly binary typed arrays (the real on-the-wire format)', () => {
    // Real bdata from the SaaS sample: Enterprise MRR 41781→52761 (f8 LE).
    const BIN = [{ type: 'scatter', mode: 'lines+markers', name: 'Enterprise',
      x: ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06'],
      y: { dtype: 'f8', bdata: 'AAAAAKBm5EAAAAAAQA/lQAAAAACAquVAAAAAACC75kAAAAAAoMXnQAAAAAAgw+lA' } }];
    const s = chartSummary('MRR', BIN);
    expect(s).toContain('Enterprise from 41,781 to 52,761');
    const { rows } = chartToTable(BIN);
    expect(rows[5]).toEqual({ '': '2026-06', Enterprise: 52761 });
  });
});

describe('chartToTable', () => {
  it('pivots x + per-trace y into a table', () => {
    const { columns, rows } = chartToTable(LINE);
    expect(columns).toEqual(['', 'Enterprise', 'Pro']);
    expect(rows[2]).toEqual({ '': 'Jun', Enterprise: 52761, Pro: 27888 });
  });

  it('renders a pie as label/value rows', () => {
    const { columns, rows } = chartToTable(PIE);
    expect(columns).toEqual(['Label', 'Value']);
    expect(rows[0]).toEqual({ Label: 'Starter', Value: 483 });
  });
});
