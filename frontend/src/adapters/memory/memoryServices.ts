import { z } from 'zod';

import { StudioError } from '../../domain/errors';
import type { StudioServices } from '../../ports';
import {
  architectureSchema,
  catalogSchema,
  toArchitecture,
  toCatalog,
  toSummary,
  validationSchema,
} from '../wire';
import rawDemoData from './demo-data.json';

const demoSchema = z.object({
  catalog: catalogSchema,
  architecture: architectureSchema.omit({ validation: true }),
  validation: validationSchema,
});

/**
 * Adapter with built-in sample data, for the public demo and for tests.
 * The fixture is validated against the same contract as real responses.
 */
export function createMemoryServices(): StudioServices {
  const demo = demoSchema.parse(rawDemoData);
  const architecture = toArchitecture({ ...demo.architecture, validation: demo.validation });
  return {
    mode: 'demo',
    catalog: { getCatalog: () => Promise.resolve(toCatalog(demo.catalog)) },
    architectures: {
      list: () => Promise.resolve([toSummary(demo.architecture)]),
      get: (id) =>
        id === architecture.id
          ? Promise.resolve(architecture)
          : Promise.reject(new StudioError('http', `Architecture ${id} not found`, 404)),
    },
    system: { getStatus: () => Promise.resolve({ backend: 'online', llm: null }) },
  };
}
