import { describe, it, expect } from 'vitest';
import { classifyIntent, busyLabel } from './intent';

// The status the assistant shows while busy MUST match what the server will
// actually do (backend classify_intent). The old client heuristic only looked
// at anchored start-words + '?', so real questions phrased as "biggest month"
// or "most customers" fell through to "Updating the dashboard…" while the
// server was answering them. These lock the mirror in place.

describe('classifyIntent (mirror of backend classify_intent)', () => {
  it('treats mid-sentence question words as questions (the regression)', () => {
    // None of these start with a question word or end in '?', but the server
    // answers every one — the old default said "Updating the dashboard…".
    expect(classifyIntent('biggest month')).toBe('question');
    expect(classifyIntent('most customers')).toBe('question');
    expect(classifyIntent('lowest revenue plan')).toBe('question');
    expect(classifyIntent('average deal size')).toBe('question');
  });

  it('classifies plain questions', () => {
    expect(classifyIntent('how many customers in June')).toBe('question');
    expect(classifyIntent('which plan has the most revenue?')).toBe('question');
  });

  it('classifies edits', () => {
    expect(classifyIntent('add a bar chart of revenue')).toBe('edit');
    expect(classifyIntent('remove the pie chart')).toBe('edit');
  });

  it('classifies edit+question as both', () => {
    expect(classifyIntent('add a chart and which plan is biggest')).toBe('both');
  });

  it('flags research', () => {
    expect(classifyIntent('research this market online')).toBe('research');
  });

  it('leaves genuinely ambiguous messages ambiguous (no false "edit")', () => {
    expect(classifyIntent('customers in June')).toBe('ambiguous');
  });
});

describe('busyLabel — status follows intent, never a stale "Updating" while answering', () => {
  it('never says "Updating the dashboard" for a question', () => {
    for (const q of ['biggest month', 'most customers', 'how many customers in June']) {
      expect(busyLabel(q)).not.toMatch(/updating/i);
    }
  });

  it('maps every intent to an honest label', () => {
    expect(busyLabel('biggest month')).toBe('Reading your data…');
    expect(busyLabel('add a bar chart')).toBe('Updating the dashboard…');
    expect(busyLabel('add a chart and which plan is biggest')).toBe('Answering and updating…');
    expect(busyLabel('research this online')).toBe('Searching the web…');
    expect(busyLabel('customers in June')).toBe('Working…');   // honest neutral, not a wrong guess
  });
});
