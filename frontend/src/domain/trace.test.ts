import { describe, expect, it } from 'vitest';

import {
  batteryExports,
  formatDuration,
  traceExports,
  waterfallRows,
  type Span,
  type Trace,
} from './trace';

function span(overrides: Partial<Span> & Pick<Span, 'id' | 'kind'>): Span {
  return {
    parentId: null,
    name: overrides.id,
    status: 'ok',
    startSeconds: 0,
    durationSeconds: 0,
    attributes: {},
    error: null,
    ...overrides,
  };
}

const trace: Trace = {
  id: 'run-1',
  spans: [
    span({ id: 'run', kind: 'run', durationSeconds: 10 }),
    span({ id: 'search', kind: 'node', parentId: 'run', startSeconds: 0, durationSeconds: 4 }),
    span({
      id: 'call-1',
      kind: 'llm',
      parentId: 'search',
      startSeconds: 1,
      durationSeconds: 2,
      status: 'error',
      error: 'timeout',
    }),
    span({ id: 'vote', kind: 'node', parentId: 'run', startSeconds: 4, durationSeconds: 6 }),
  ],
  summary: {
    status: 'completed',
    durationSeconds: 10,
    nodeCount: 2,
    llmCalls: 1,
    promptTokens: 10,
    completionTokens: 3,
    errorCount: 1,
    unsupportedFigures: [],
    slowestNode: { name: 'vote', durationSeconds: 6 },
  },
};

const ALL = { kinds: ['run', 'node', 'llm'] as const, onlyErrors: false };

describe('waterfall rows', () => {
  it('nests each span under its parent and positions bars as a share of the run', () => {
    const rows = waterfallRows(trace, ALL);
    expect(rows.map((row) => [row.span.id, row.depth])).toEqual([
      ['run', 0],
      ['search', 1],
      ['call-1', 2],
      ['vote', 1],
    ]);
    expect(rows[3]?.leftPercent).toBeCloseTo(40);
    expect(rows[3]?.widthPercent).toBeCloseTo(60);
  });

  it('gives very short spans a visible minimum width and keeps bars inside the run', () => {
    const tiny: Trace = {
      ...trace,
      spans: [
        span({ id: 'run', kind: 'run', durationSeconds: 100 }),
        span({ id: 'x', kind: 'node', parentId: 'run', startSeconds: 99.99, durationSeconds: 0 }),
      ],
    };
    const row = waterfallRows(tiny, ALL)[1];
    expect(row?.widthPercent).toBeGreaterThanOrEqual(0.5);
    expect((row?.leftPercent ?? 0) + (row?.widthPercent ?? 0)).toBeLessThanOrEqual(100);
  });

  it('filters by kind and by errors while keeping the nesting depth', () => {
    const nodes = waterfallRows(trace, { kinds: ['node'], onlyErrors: false });
    expect(nodes.map((row) => row.span.id)).toEqual(['search', 'vote']);
    const errors = waterfallRows(trace, { ...ALL, onlyErrors: true });
    expect(errors.map((row) => [row.span.id, row.depth])).toEqual([['call-1', 2]]);
  });

  it('survives a trace whose run has no duration', () => {
    const empty: Trace = { ...trace, spans: [span({ id: 'run', kind: 'run' })] };
    expect(waterfallRows(empty, ALL)[0]?.widthPercent).toBe(100);
  });
});

describe('formatting and exports', () => {
  it.each([
    [0.42, '420 ms'],
    [6.5087, '6.5 s'],
    [65, '1 min 5 s'],
    [0, '0 ms'],
  ])('formats %s seconds as %s', (seconds, text) => {
    expect(formatDuration(seconds)).toBe(text);
  });

  it('lists the downloads of a run and of a battery, labelled by format only', () => {
    expect(traceExports('a b')).toEqual([
      { format: 'JSONL', url: '/api/runs/a%20b/trace.jsonl', filename: 'trace-a b.jsonl' },
      { format: 'OTLP', url: '/api/runs/a%20b/trace.otlp.json', filename: 'trace-a b.otlp.json' },
      { format: 'Markdown', url: '/api/runs/a%20b/report.md', filename: 'report-a b.md' },
    ]);
    expect(batteryExports('e1')).toEqual([
      { format: 'CSV', url: '/api/experiments/e1/trace.csv', filename: 'battery-e1.csv' },
    ]);
  });
});
