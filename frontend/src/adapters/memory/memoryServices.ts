import { z } from 'zod';

import { IDLE_BATTERY } from '../../domain/battery';
import { StudioError } from '../../domain/errors';
import type { Point } from '../../domain/editor/model';
import type { StudioServices } from '../../ports';
import { createLocalStorageDrafts } from '../drafts/localStorageDrafts';
import {
  architectureSchema,
  catalogSchema,
  definitionToWire,
  toArchitecture,
  toCatalog,
  toSummary,
  toValidation,
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
  const builtinDefinition = JSON.stringify(definitionToWire(architecture.definition));
  const layouts = new Map<string, Record<string, Point>>();
  return {
    mode: 'demo',
    catalog: { getCatalog: () => Promise.resolve(toCatalog(demo.catalog)) },
    architectures: {
      list: () => Promise.resolve([toSummary(demo.architecture)]),
      get: (id) =>
        id === architecture.id
          ? Promise.resolve(architecture)
          : Promise.reject(new StudioError('http', `Architecture ${id} not found`, 404)),
      save: () => Promise.reject(new StudioError('unavailable', 'Saving needs the backend')),
    },
    system: { getStatus: () => Promise.resolve({ backend: 'online', llm: null }) },
    // The validator runs on the Python backend, so only the built-in report is known here.
    validation: {
      validate: (definition) =>
        JSON.stringify(definitionToWire(definition)) === builtinDefinition
          ? Promise.resolve(toValidation(demo.validation))
          : Promise.reject(new StudioError('unavailable', 'Validation needs the backend')),
    },
    layouts: {
      get: (architectureId) => Promise.resolve({ ...layouts.get(architectureId) }),
      save: (architectureId, positions) => {
        layouts.set(architectureId, { ...positions });
        return Promise.resolve();
      },
    },
    drafts: createLocalStorageDrafts(),
    // Running needs the Python backend, and benchmark questions are never offered here.
    runs: {
      run: () => Promise.reject(new StudioError('unavailable', 'Running needs the backend')),
      get: (id) => Promise.reject(new StudioError('http', `Run ${id} not found`, 404)),
    },
    batteries: {
      start: () => Promise.reject(new StudioError('unavailable', 'Batteries need the backend')),
      current: () => Promise.resolve(IDLE_BATTERY),
      stop: () => Promise.resolve(IDLE_BATTERY),
    },
    experiments: { list: () => Promise.resolve([]) },
    models: { list: () => Promise.resolve([]) },
    questions: {
      list: () => Promise.reject(new StudioError('unavailable', 'Questions need the backend')),
    },
  };
}
