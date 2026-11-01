import type { z } from 'zod';

import { toWireExperiment } from '../../domain/experiment';
import { StudioError } from '../../domain/errors';
import type { SystemStatus } from '../../domain/types';
import type { StudioServices } from '../../ports';
import { createLocalStorageDrafts } from '../drafts/localStorageDrafts';
import {
  architectureListSchema,
  batterySchema,
  experimentListSchema,
  architectureSchema,
  catalogSchema,
  definitionToWire,
  layoutSchema,
  modelsSchema,
  questionsSchema,
  runRecordSchema,
  savedRecordSchema,
  statusSchema,
  toArchitecture,
  toBatteryStatus,
  toCatalog,
  toExperimentSummaries,
  toModels,
  toQuestions,
  toRunRecord,
  toStatus,
  toSummary,
  toValidation,
  validationSchema,
} from '../wire';

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

async function requestJson<S extends z.ZodType>(
  fetchImpl: FetchLike,
  path: string,
  schema: S,
  send?: { method: 'POST' | 'PUT'; body: unknown },
): Promise<z.output<S>> {
  const init: RequestInit = { headers: { Accept: 'application/json' } };
  if (send) {
    init.method = send.method;
    init.headers = { ...init.headers, 'Content-Type': 'application/json' };
    init.body = JSON.stringify(send.body);
  }
  let response: Response;
  try {
    response = await fetchImpl(path, init);
  } catch (error) {
    throw new StudioError('network', error instanceof Error ? error.message : 'Network error');
  }
  if (!response.ok) {
    throw new StudioError('http', `${path} responded ${response.status}`, response.status);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new StudioError('contract', `${path} did not return JSON`);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new StudioError('contract', `${path} returned an unexpected shape`);
  }
  return parsed.data;
}

const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError';

const layoutPath = (architectureId: string) =>
  `/api/architectures/${encodeURIComponent(architectureId)}/layout`;

/** Adapter that talks to the Python backend over HTTP. */
export function createHttpServices(
  fetchImpl: FetchLike = (input, init) => fetch(input, init),
): StudioServices {
  return {
    mode: 'live',
    catalog: {
      getCatalog: async () =>
        toCatalog(await requestJson(fetchImpl, '/api/catalog', catalogSchema)),
    },
    architectures: {
      list: async () =>
        (
          await requestJson(fetchImpl, '/api/architectures', architectureListSchema)
        ).architectures.map(toSummary),
      get: async (id) =>
        toArchitecture(
          await requestJson(
            fetchImpl,
            `/api/architectures/${encodeURIComponent(id)}`,
            architectureSchema,
          ),
        ),
      save: async (definition) => {
        const known = new Set(
          (
            await requestJson(fetchImpl, '/api/architectures', architectureListSchema)
          ).architectures.map((item) => item.id),
        );
        const record = await requestJson(fetchImpl, '/api/architectures', savedRecordSchema, {
          method: 'POST',
          body: definitionToWire(definition),
        });
        const architecture = toArchitecture(
          await requestJson(
            fetchImpl,
            `/api/architectures/${encodeURIComponent(record.id)}`,
            architectureSchema,
          ),
        );
        return { architecture, created: !known.has(record.id) };
      },
    },
    system: {
      getStatus: async (): Promise<SystemStatus> => {
        try {
          return toStatus(await requestJson(fetchImpl, '/api/status', statusSchema));
        } catch (error) {
          if (error instanceof StudioError && error.kind === 'network') {
            return { backend: 'offline', llm: null };
          }
          return { backend: 'online', llm: null };
        }
      },
    },
    validation: {
      validate: async (definition) =>
        toValidation(
          await requestJson(fetchImpl, '/api/architectures/validate', validationSchema, {
            method: 'POST',
            body: definitionToWire(definition),
          }),
        ),
    },
    layouts: {
      get: async (architectureId) =>
        (await requestJson(fetchImpl, layoutPath(architectureId), layoutSchema)).layout.nodes,
      save: async (architectureId, positions) => {
        await requestJson(fetchImpl, layoutPath(architectureId), layoutSchema, {
          method: 'PUT',
          body: { nodes: positions },
        });
      },
    },
    drafts: createLocalStorageDrafts(),
    runs: {
      run: async (request, signal) => {
        const body = {
          task_id: request.taskId,
          question: request.question,
          file_name: request.fileName,
          experiment: toWireExperiment(request.settings, request.architectureId),
        };
        let response: Response;
        try {
          response = await fetchImpl('/api/run', {
            method: 'POST',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            ...(signal ? { signal } : {}),
          });
        } catch (error) {
          if (isAbort(error)) throw new StudioError('aborted', 'The wait was cancelled');
          throw new StudioError(
            'network',
            error instanceof Error ? error.message : 'Network error',
          );
        }
        const payload: unknown = await response.json().catch(() => null);
        const fields = (payload && typeof payload === 'object' ? payload : {}) as {
          run_id?: unknown;
          error?: unknown;
        };
        if (typeof fields.run_id !== 'string') {
          const reason =
            typeof fields.error === 'string' ? fields.error : `responded ${response.status}`;
          throw new StudioError('http', `/api/run ${reason}`, response.status);
        }
        return toRunRecord(
          await requestJson(
            fetchImpl,
            `/api/runs/${encodeURIComponent(fields.run_id)}`,
            runRecordSchema,
          ),
        );
      },
      get: async (id) =>
        toRunRecord(
          await requestJson(fetchImpl, `/api/runs/${encodeURIComponent(id)}`, runRecordSchema),
        ),
    },
    batteries: {
      start: async (request) =>
        toBatteryStatus(
          await requestJson(fetchImpl, '/api/batteries', batterySchema, {
            method: 'POST',
            body:
              request.kind === 'resume'
                ? { resume_id: request.experimentId }
                : {
                    experiment: toWireExperiment(request.settings, request.architectureId),
                    limit: request.limit,
                  },
          }),
        ),
      current: async () =>
        toBatteryStatus(await requestJson(fetchImpl, '/api/batteries/current', batterySchema)),
      stop: async () =>
        toBatteryStatus(
          await requestJson(fetchImpl, '/api/batteries/stop', batterySchema, {
            method: 'POST',
            body: {},
          }),
        ),
    },
    experiments: {
      list: async () =>
        toExperimentSummaries(
          await requestJson(fetchImpl, '/api/experiments', experimentListSchema),
        ),
    },
    models: {
      list: async () => toModels(await requestJson(fetchImpl, '/api/models', modelsSchema)),
    },
    questions: {
      list: async () =>
        toQuestions(await requestJson(fetchImpl, '/api/questions', questionsSchema)),
    },
  };
}
