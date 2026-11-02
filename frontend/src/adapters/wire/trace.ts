/** Wire format of the backend's traces and battery insights, and its translation into the domain model. */
import { z } from 'zod';

import type { Insights, TaskOutcome } from '../../domain/insights';
import type { Span, SpanAttributes, SpanKind, Trace } from '../../domain/trace';

const attributeValue = z.unknown().transform((value): string | number | boolean => {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }
  if (Array.isArray(value)) return value.map(String).join(', ');
  return JSON.stringify(value) ?? '';
});

const spanSchema = z.object({
  span_id: z.string(),
  parent_id: z.string().nullable(),
  kind: z.enum(['run', 'node', 'llm']),
  name: z.string(),
  status: z.enum(['ok', 'error']),
  start_offset_seconds: z.number(),
  duration_seconds: z.number(),
  attributes: z.record(z.string(), attributeValue).default({}),
  error: z.string().nullish(),
});

export const traceSchema = z.object({
  trace_id: z.string(),
  spans: z.array(spanSchema),
  summary: z.object({
    status: z.string().nullish(),
    duration_seconds: z.number().nullish(),
    node_count: z.number(),
    llm_calls: z.number(),
    prompt_tokens: z.number(),
    completion_tokens: z.number(),
    error_count: z.number(),
    unsupported_figures: z.array(z.string()).default([]),
    slowest_node: z.object({ name: z.string(), duration_seconds: z.number() }).nullish(),
  }),
});

export const spanPayloadSchema = z.record(z.string(), z.unknown());

function toAttributes(wire: Record<string, z.output<typeof attributeValue>>): SpanAttributes {
  return { ...wire };
}

function toSpan(wire: z.output<typeof spanSchema>): Span {
  return {
    id: wire.span_id,
    parentId: wire.parent_id,
    kind: wire.kind satisfies SpanKind,
    name: wire.name,
    status: wire.status,
    startSeconds: wire.start_offset_seconds,
    durationSeconds: wire.duration_seconds,
    attributes: toAttributes(wire.attributes),
    error: wire.error ?? null,
  };
}

export function toTrace(wire: z.output<typeof traceSchema>): Trace {
  const summary = wire.summary;
  return {
    id: wire.trace_id,
    spans: wire.spans.map(toSpan),
    summary: {
      status: summary.status ?? null,
      durationSeconds: summary.duration_seconds ?? null,
      nodeCount: summary.node_count,
      llmCalls: summary.llm_calls,
      promptTokens: summary.prompt_tokens,
      completionTokens: summary.completion_tokens,
      errorCount: summary.error_count,
      unsupportedFigures: summary.unsupported_figures,
      slowestNode: summary.slowest_node
        ? {
            name: summary.slowest_node.name,
            durationSeconds: summary.slowest_node.duration_seconds,
          }
        : null,
    },
  };
}

export const insightsSchema = z.object({
  totals: z.object({
    answered: z.number(),
    scored: z.number(),
    correct: z.number(),
    accuracy: z.number().nullable(),
    mean_seconds: z.number().nullable(),
    completion_tokens: z.number(),
    technical_errors: z.number(),
  }),
  routes: z.array(
    z.object({
      route: z.string(),
      count: z.number(),
      scored: z.number(),
      correct: z.number(),
      accuracy: z.number().nullable(),
      mean_seconds: z.number().nullable(),
    }),
  ),
  stages: z.array(
    z.object({
      stage: z.string(),
      total_seconds: z.number(),
      mean_seconds: z.number(),
      tasks: z.number(),
      share: z.number(),
    }),
  ),
  failures: z.object({
    wrong_answers: z.number(),
    errors: z.array(z.object({ message: z.string(), count: z.number() })),
    truncated_calls: z.number(),
  }),
  tasks: z.array(
    z.object({
      task_id: z.string(),
      outcome: z.enum(['correct', 'wrong', 'error', 'unscored']),
    }),
  ),
  slowest_tasks: z.array(
    z.object({
      task_id: z.string(),
      duration_seconds: z.number(),
      slowest_stage: z.string().nullable(),
    }),
  ),
});

export function toInsights(wire: z.output<typeof insightsSchema>): Insights {
  return {
    totals: {
      answered: wire.totals.answered,
      scored: wire.totals.scored,
      correct: wire.totals.correct,
      accuracy: wire.totals.accuracy,
      meanSeconds: wire.totals.mean_seconds,
      completionTokens: wire.totals.completion_tokens,
      technicalErrors: wire.totals.technical_errors,
    },
    routes: wire.routes.map((route) => ({
      route: route.route,
      count: route.count,
      scored: route.scored,
      correct: route.correct,
      accuracy: route.accuracy,
      meanSeconds: route.mean_seconds,
    })),
    stages: wire.stages.map((stage) => ({
      stage: stage.stage,
      totalSeconds: stage.total_seconds,
      meanSeconds: stage.mean_seconds,
      tasks: stage.tasks,
      share: stage.share,
    })),
    failures: {
      wrongAnswers: wire.failures.wrong_answers,
      errors: wire.failures.errors,
      truncatedCalls: wire.failures.truncated_calls,
    },
    tasks: wire.tasks.map((task) => ({
      taskId: task.task_id,
      outcome: task.outcome satisfies TaskOutcome,
    })),
    slowestTasks: wire.slowest_tasks.map((task) => ({
      taskId: task.task_id,
      durationSeconds: task.duration_seconds,
      slowestStage: task.slowest_stage,
    })),
  };
}
