/** Wire format of the backend's stored experiments, scoring and comparison and its translation into the domain model. */
import { z } from 'zod';

import { PIPELINE_VERSIONS, type PipelineVersion } from '../../domain/experiment';
import type {
  Comparison,
  ExperimentAnswer,
  ExperimentRecord,
  Score,
  TaskChange,
} from '../../domain/history';

const scoreSchema = z.object({
  score: z.number().nullish(),
  correct_count: z.number(),
  total_attempted: z.number(),
});

function toScore(wire: z.output<typeof scoreSchema> | null | undefined): Score | null {
  if (!wire) return null;
  return {
    percent:
      wire.score ??
      (wire.total_attempted > 0 ? (wire.correct_count / wire.total_attempted) * 100 : 0),
    correct: wire.correct_count,
    attempted: wire.total_attempted,
  };
}

export const experimentListSchema = z.object({
  experiments: z.array(
    z.object({
      id: z.string(),
      status: z.string().nullish(),
      created_at: z.string().nullish(),
      total_questions: z.number().nullish(),
      average_duration_seconds: z.number().nullish(),
      answers: z
        .array(
          z.object({
            task_id: z.string(),
            question: z.string().nullish(),
            file_name: z.string().nullish(),
            submitted_answer: z.string().nullish(),
            error: z.string().nullish(),
            route: z.string().nullish(),
            duration_seconds: z.number().nullish(),
            run_id: z.string().nullish(),
            locally_correct: z.boolean().nullish(),
          }),
        )
        .default([]),
      config: z
        .object({
          name: z.string().nullish(),
          pipeline_version: z.string().nullish(),
          architecture: z.string().nullish(),
        })
        .nullish(),
      local_score: scoreSchema.nullish(),
      score: scoreSchema.nullish(),
    }),
  ),
});

const isPipelineVersion = (value: string): value is PipelineVersion =>
  (PIPELINE_VERSIONS as readonly string[]).includes(value);

export function toExperimentRecords(
  wire: z.output<typeof experimentListSchema>,
): ExperimentRecord[] {
  return wire.experiments.map((record) => {
    const version = record.config?.pipeline_version ?? '';
    const answers: ExperimentAnswer[] = record.answers.map((answer) => ({
      taskId: answer.task_id,
      question: answer.question ?? '',
      fileName: answer.file_name ?? '',
      answer: answer.submitted_answer ?? '',
      error: answer.error ?? '',
      route: answer.route ?? '',
      durationSeconds: answer.duration_seconds ?? null,
      runId: answer.run_id ?? null,
      locallyCorrect: answer.locally_correct ?? null,
    }));
    return {
      id: record.id,
      status: record.status ?? 'completed',
      name: record.config?.name ?? record.id,
      pipelineVersion: isPipelineVersion(version) ? version : null,
      architecture: record.config?.architecture ?? null,
      completed: answers.length,
      total: record.total_questions ?? answers.length,
      createdAt: record.created_at ?? null,
      averageSeconds: record.average_duration_seconds ?? null,
      answers,
      localScore: toScore(record.local_score),
      officialScore: toScore(record.score),
    };
  });
}

export const evaluateSchema = scoreSchema;
export const submitSchema = scoreSchema.extend({ saved: z.boolean().default(false) });
export const deletedSchema = z.object({ deleted: z.boolean() });

export { toScore };

const change = z.enum(['gained', 'lost', 'unchanged', 'unknown']);
const range = z.object({ min: z.number(), max: z.number(), mean: z.number() });

export const comparisonSchema = z.object({
  base_group: z.string(),
  experiments: z.array(
    z.object({
      id: z.string(),
      name: z.string().nullish(),
      status: z.string().nullish(),
      group: z.string(),
      metrics: z.object({
        answered: z.number(),
        correct: z.number().nullish(),
        accuracy: z.number().nullish(),
        mean_seconds: z.number().nullish(),
        median_seconds: z.number().nullish(),
        p95_seconds: z.number().nullish(),
        technical_errors: z.number().default(0),
        truncated_calls: z.number().default(0),
      }),
    }),
  ),
  groups: z.array(
    z.object({
      key: z.string(),
      experiment_ids: z.array(z.string()),
      runs: z.number(),
      accuracy: range.nullish(),
      mean_seconds: range.nullish(),
      versus_base: z
        .object({
          gained: z.number(),
          lost: z.number(),
          unchanged: z.number(),
          unknown: z.number(),
          accuracy_difference: z.object({
            delta: z.number().nullish(),
            assessment: z.string(),
          }),
          mean_seconds_delta: z.number().nullish(),
        })
        .nullish(),
    }),
  ),
  comparability: z.object({
    same_task_set: z.boolean(),
    same_code: z.boolean().nullish(),
    same_architecture: z.boolean(),
    config_differences: z.record(z.string(), z.unknown()).default({}),
    warnings: z.array(z.string()).default([]),
  }),
  tasks: z.array(
    z.object({
      task_id: z.string(),
      outcomes: z.record(
        z.string(),
        z.object({
          correct: z.boolean().nullish(),
          route: z.string().nullish(),
          seconds: z.number().nullish(),
          error: z.boolean().default(false),
          versus_base: change.nullish(),
        }),
      ),
    }),
  ),
});

export function toComparison(wire: z.output<typeof comparisonSchema>): Comparison {
  return {
    baseGroup: wire.base_group,
    experiments: wire.experiments.map((item) => ({
      id: item.id,
      name: item.name ?? item.id,
      status: item.status ?? 'completed',
      group: item.group,
      metrics: {
        answered: item.metrics.answered,
        correct: item.metrics.correct ?? null,
        accuracy: item.metrics.accuracy ?? null,
        meanSeconds: item.metrics.mean_seconds ?? null,
        medianSeconds: item.metrics.median_seconds ?? null,
        p95Seconds: item.metrics.p95_seconds ?? null,
        technicalErrors: item.metrics.technical_errors,
        truncatedCalls: item.metrics.truncated_calls,
      },
    })),
    groups: wire.groups.map((group) => ({
      key: group.key,
      experimentIds: group.experiment_ids,
      runs: group.runs,
      accuracy: group.accuracy ?? null,
      meanSeconds: group.mean_seconds ?? null,
      versusBase: group.versus_base
        ? {
            gained: group.versus_base.gained,
            lost: group.versus_base.lost,
            unchanged: group.versus_base.unchanged,
            unknown: group.versus_base.unknown,
            accuracyDelta: group.versus_base.accuracy_difference.delta ?? null,
            assessment: group.versus_base.accuracy_difference.assessment,
            meanSecondsDelta: group.versus_base.mean_seconds_delta ?? null,
          }
        : null,
    })),
    comparability: {
      sameTaskSet: wire.comparability.same_task_set,
      sameCode: wire.comparability.same_code ?? null,
      sameArchitecture: wire.comparability.same_architecture,
      configDifferences: Object.keys(wire.comparability.config_differences),
      warnings: wire.comparability.warnings,
    },
    tasks: wire.tasks.map((task) => ({
      taskId: task.task_id,
      outcomes: Object.fromEntries(
        Object.entries(task.outcomes).map(([id, outcome]) => [
          id,
          {
            correct: outcome.correct ?? null,
            route: outcome.route ?? null,
            seconds: outcome.seconds ?? null,
            error: outcome.error,
            versusBase: (outcome.versus_base ?? null) as TaskChange | null,
          },
        ]),
      ),
    })),
  };
}
