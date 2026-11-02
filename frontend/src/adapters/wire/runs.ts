/** Wire format of the backend's runs, models and GAIA questions and its translation into the domain model. */
import { z } from 'zod';

import type { GaiaQuestion, ModelCatalog, ModelOption, RunRecord } from '../../domain/run';

export const runRecordSchema = z.object({
  id: z.string(),
  status: z.string(),
  duration_seconds: z.number().default(0),
  steps: z
    .array(
      z.object({
        node: z.string(),
        duration_seconds: z.number().default(0),
        update: z.record(z.string(), z.unknown()).nullish(),
        error: z.string().nullish(),
      }),
    )
    .default([]),
  architecture: z
    .object({
      engine: z.string(),
      id: z.string().nullish(),
      version: z.number().nullish(),
      content_sha256: z.string().nullish(),
    })
    .nullish(),
  task: z
    .object({
      question: z.string().default(''),
      experiment: z.object({ model: z.object({ model_id: z.string() }).nullish() }).nullish(),
    })
    .nullish(),
  result: z
    .object({ submitted_answer: z.string().nullish(), route: z.string().nullish() })
    .nullish(),
  error: z.string().nullish(),
});

const modelEntry = z.object({ provider: z.string(), model_id: z.string() });

export const modelsSchema = z.object({
  models: z.array(modelEntry),
  vision_models: z.array(modelEntry).default([]),
});

export const questionsSchema = z.array(
  z.object({
    task_id: z.string(),
    question: z.string(),
    Level: z.union([z.string(), z.number()]).nullish(),
    file_name: z.string().nullish(),
  }),
);

export function toRunRecord(wire: z.output<typeof runRecordSchema>): RunRecord {
  const architecture = wire.architecture;
  return {
    id: wire.id,
    status: wire.status === 'completed' ? 'completed' : 'error',
    durationSeconds: wire.duration_seconds,
    steps: wire.steps.map((step) => ({
      node: step.node,
      durationSeconds: step.duration_seconds,
      error: step.error ?? null,
      updatedFields: Object.keys(step.update ?? {}),
    })),
    architecture: architecture
      ? {
          engine: architecture.engine,
          id: architecture.id ?? null,
          version: architecture.version ?? null,
          contentSha256: architecture.content_sha256 ?? null,
        }
      : null,
    question: wire.task?.question ?? '',
    answer: wire.result?.submitted_answer ?? null,
    route: wire.result?.route ?? null,
    error: wire.error ?? null,
    modelId: wire.task?.experiment?.model?.model_id ?? null,
  };
}

const MODEL_PROVIDERS: readonly ModelOption['provider'][] = ['configured', 'ollama'];

function toModelOptions(entries: z.output<typeof modelEntry>[]): ModelOption[] {
  return entries.flatMap((model) => {
    const provider = MODEL_PROVIDERS.find((known) => known === model.provider);
    return provider ? [{ provider, modelId: model.model_id }] : [];
  });
}

export function toModels(wire: z.output<typeof modelsSchema>): ModelCatalog {
  return { models: toModelOptions(wire.models), visionModels: toModelOptions(wire.vision_models) };
}

export function toQuestions(wire: z.output<typeof questionsSchema>): GaiaQuestion[] {
  return wire.map((item) => ({
    taskId: item.task_id,
    question: item.question,
    fileName: item.file_name ?? '',
    level: String(item.Level ?? ''),
  }));
}
