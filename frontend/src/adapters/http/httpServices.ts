import type { z } from 'zod';

import { StudioError } from '../../domain/errors';
import type { SystemStatus } from '../../domain/types';
import type { StudioServices } from '../../ports';
import {
  architectureListSchema,
  architectureSchema,
  catalogSchema,
  statusSchema,
  toArchitecture,
  toCatalog,
  toStatus,
  toSummary,
} from '../wire';

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

async function getJson<S extends z.ZodType>(
  fetchImpl: FetchLike,
  path: string,
  schema: S,
): Promise<z.output<S>> {
  let response: Response;
  try {
    response = await fetchImpl(path, { headers: { Accept: 'application/json' } });
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

/** Adapter that talks to the Python backend over HTTP. */
export function createHttpServices(
  fetchImpl: FetchLike = (input, init) => fetch(input, init),
): StudioServices {
  return {
    mode: 'live',
    catalog: {
      getCatalog: async () => toCatalog(await getJson(fetchImpl, '/api/catalog', catalogSchema)),
    },
    architectures: {
      list: async () =>
        (await getJson(fetchImpl, '/api/architectures', architectureListSchema)).architectures.map(
          toSummary,
        ),
      get: async (id) =>
        toArchitecture(
          await getJson(
            fetchImpl,
            `/api/architectures/${encodeURIComponent(id)}`,
            architectureSchema,
          ),
        ),
    },
    system: {
      getStatus: async (): Promise<SystemStatus> => {
        try {
          return toStatus(await getJson(fetchImpl, '/api/status', statusSchema));
        } catch (error) {
          if (error instanceof StudioError && error.kind === 'network') {
            return { backend: 'offline', llm: null };
          }
          return { backend: 'online', llm: null };
        }
      },
    },
  };
}
