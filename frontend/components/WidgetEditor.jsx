'use client';

import { useState } from 'react';
import Modal from './ui/Modal';
import Field from './ui/Field';
import Input, { Select } from './ui/Input';
import Button from './ui/Button';

// Manual widget editor — the point-and-click alternative to the chat assistant.
// Emits the same structured specs the ops engine consumes, so hand edits and
// chat edits are interchangeable.

const CHART_TYPES = ['bar', 'line', 'area', 'pie', 'scatter', 'histogram', 'box', 'treemap', 'heatmap'];
const AGGS = ['sum', 'mean', 'count', 'min', 'max', 'median'];

// Which fields each chart type actually uses.
const NEEDS = {
  bar: ['x', 'y', 'group_by', 'agg'],
  line: ['x', 'y', 'group_by', 'agg'],
  area: ['x', 'y', 'group_by', 'agg'],
  pie: ['x', 'y', 'agg'],
  scatter: ['x', 'y', 'group_by'],
  histogram: ['x'],
  box: ['y', 'group_by'],
  treemap: ['x', 'y', 'group_by', 'agg'],
  heatmap: [],
};

export default function WidgetEditor({ mode, columns, initial, busy, onSubmit, onClose }) {
  const isMetric = mode === 'metric';
  const [chartType, setChartType] = useState(initial?.chart_type || 'bar');
  const [x, setX] = useState(initial?.x || '');
  const [y, setY] = useState(initial?.y || '');
  const [groupBy, setGroupBy] = useState(initial?.group_by || '');
  const [agg, setAgg] = useState(initial?.agg || 'sum');
  const [title, setTitle] = useState(initial?.title || '');
  const [column, setColumn] = useState(initial?.column || '');
  const [label, setLabel] = useState(initial?.label || '');

  const numeric = columns.filter((c) => c.type === 'numeric').map((c) => c.name);
  const all = columns.map((c) => c.name);
  const opt = (names) => [{ value: '', label: '—' }, ...names.map((n) => ({ value: n, label: n }))];
  const needs = NEEDS[chartType] || [];

  const submit = () => {
    if (isMetric) {
      onSubmit({ column, agg, label: label.trim() || undefined });
    } else {
      onSubmit({
        chart_type: chartType,
        x: needs.includes('x') ? x || null : null,
        y: needs.includes('y') ? y || null : null,
        group_by: needs.includes('group_by') ? groupBy || null : null,
        agg: needs.includes('agg') ? agg : null,
        title: title.trim() || undefined,
      });
    }
  };

  const valid = isMetric
    ? !!column
    : (!needs.includes('x') || !!x) && (!needs.includes('y') || !!y);

  return (
    <Modal
      title={isMetric ? (initial ? 'Edit metric' : 'Add metric') : initial ? 'Edit chart' : 'Add chart'}
      onClose={onClose}
      width="w-[440px]"
    >
      {isMetric ? (
        <>
          <Field label="Column">
            <Select value={column} onChange={(e) => setColumn(e.target.value)} options={opt(numeric)} />
          </Field>
          <Field label="Aggregation">
            <Select value={agg} onChange={(e) => setAgg(e.target.value)} options={AGGS} />
          </Field>
          <Field label="Label" hint="Optional — shown on the metric card.">
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={column ? `${agg} ${column}` : 'e.g. Total revenue'} />
          </Field>
        </>
      ) : (
        <>
          <Field label="Chart type">
            <Select value={chartType} onChange={(e) => setChartType(e.target.value)} options={CHART_TYPES} />
          </Field>
          {needs.includes('x') && (
            <Field label={chartType === 'pie' || chartType === 'treemap' ? 'Category (names)' : 'X axis'}>
              <Select value={x} onChange={(e) => setX(e.target.value)} options={opt(all)} />
            </Field>
          )}
          {needs.includes('y') && (
            <Field label={chartType === 'pie' || chartType === 'treemap' ? 'Values' : 'Y axis'}>
              <Select value={y} onChange={(e) => setY(e.target.value)} options={opt(numeric)} />
            </Field>
          )}
          {needs.includes('group_by') && (
            <Field label="Group by" hint="Optional — one series/segment per value.">
              <Select value={groupBy} onChange={(e) => setGroupBy(e.target.value)} options={opt(all)} />
            </Field>
          )}
          {needs.includes('agg') && (
            <Field label="Aggregation">
              <Select value={agg} onChange={(e) => setAgg(e.target.value)} options={AGGS} />
            </Field>
          )}
          {chartType === 'heatmap' && (
            <p className="text-[12px] text-[var(--faint)] mb-4">
              Correlation heatmap across all numeric columns — no configuration needed.
            </p>
          )}
          <Field label="Title" hint="Optional.">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Revenue by region" />
          </Field>
        </>
      )}

      <div className="flex justify-end gap-2 mt-5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={submit} disabled={busy || !valid}>
          {busy ? 'Applying…' : initial ? 'Update' : 'Add'}
        </Button>
      </div>
    </Modal>
  );
}
