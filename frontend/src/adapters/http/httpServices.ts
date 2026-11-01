import type { z } from 'zod';

import { StudioError } from '../../domain/errors';
import type { SystemStatus } from '../../domain/types';
import type { StudioServices } from '../../ports';
import { createLocalStorageDrafts } from '../drafts/localStorageDrafts';
import {
  architectureListSchema,
  architectureSchema,
  catalogSchema,
  definitionToWire,
  layoutSchema,
  statusSchema,
  toArchitecture,
  toCatalog,
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
  };
}
