/** Traces of a run as spans, and the pure helpers that prepare them for display and export. */

export type SpanKind = 'run' | 'node' | 'llm';
export type SpanAttributes = Record<string, string | number | boolean>;

export interface Span {
  id: string;
  parentId: string | null;
  kind: SpanKind;
  name: string;
  status: 'ok' | 'error';
  startSeconds: number;
  durationSeconds: number;
  attributes: SpanAttributes;
  error: string | null;
}

export interface TraceSummary {
  status: string | null;
  durationSeconds: number | null;
  nodeCount: number;
  llmCalls: number;
  promptTokens: number;
  completionTokens: number;
  errorCount: number;
  /** Figures cited by a decision or answer that no collected source contains. */
  unsupportedFigures: string[];
  slowestNode: { name: string; durationSeconds: number } | null;
}

export interface Trace {
  id: string;
  spans: Span[];
  summary: TraceSummary;
}

/** The heavy content of one span, loaded only when it is opened. */
export type SpanPayload = Record<string, unknown>;

export interface SpanFilter {
  kinds: readonly SpanKind[];
  onlyErrors: boolean;
}

export interface WaterfallRow {
  span: Span;
  depth: number;
  leftPercent: number;
  widthPercent: number;
}

const MIN_WIDTH_PERCENT = 0.5;
const MAX_DEPTH = 20;

function depthOf(span: Span, byId: Map<string, Span>): number {
  let depth = 0;
  let parent = span.parentId ? byId.get(span.parentId) : undefined;
  while (parent && depth < MAX_DEPTH) {
    depth += 1;
    parent = parent.parentId ? byId.get(parent.parentId) : undefined;
  }
  return depth;
}

function totalSeconds(trace: Trace): number {
  const root = trace.spans.find((span) => span.kind === 'run');
  return (
    root?.durationSeconds ||
    Math.max(0, ...trace.spans.map((span) => span.startSeconds + span.durationSeconds))
  );
}

/** One row per visible span: its nesting depth and its bar as a share of the whole run. */
export function waterfallRows(trace: Trace, filter: SpanFilter): WaterfallRow[] {
  const byId = new Map(trace.spans.map((span) => [span.id, span]));
  const total = totalSeconds(trace);
  return trace.spans
    .filter(
      (span) => filter.kinds.includes(span.kind) && (!filter.onlyErrors || span.status === 'error'),
    )
    .map((span) => {
      const depth = depthOf(span, byId);
      if (total <= 0) return { span, depth, leftPercent: 0, widthPercent: 100 };
      const width = Math.min(
        100,
        Math.max(MIN_WIDTH_PERCENT, (span.durationSeconds / total) * 100),
      );
      const left = Math.min(100 - width, Math.max(0, (span.startSeconds / total) * 100));
      return { span, depth, leftPercent: left, widthPercent: width };
    });
}

/** Seconds as a short label: milliseconds below one second, minutes from sixty. */
export function formatDuration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${Math.round(seconds * 10) / 10} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`;
}

export interface ExportLink {
  format: string;
  url: string;
  filename: string;
}

/** Downloads of the trace of one run, labelled by format. */
export function traceExports(runId: string): ExportLink[] {
  const base = `/api/runs/${encodeURIComponent(runId)}`;
  return [
    { format: 'JSONL', url: `${base}/trace.jsonl`, filename: `trace-${runId}.jsonl` },
    { format: 'OTLP', url: `${base}/trace.otlp.json`, filename: `trace-${runId}.otlp.json` },
    { format: 'Markdown', url: `${base}/report.md`, filename: `report-${runId}.md` },
  ];
}

/** Downloads of the table of one battery. */
export function batteryExports(experimentId: string): ExportLink[] {
  return [
    {
      format: 'CSV',
      url: `/api/experiments/${encodeURIComponent(experimentId)}/trace.csv`,
      filename: `battery-${experimentId}.csv`,
    },
  ];
}
