import { describe, expect, it } from 'vitest';

import type { AgentDefinition } from '../domain/types';
import { createHttpServices, type FetchLike } from './http/httpServices';

function respond(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

interface Sent {
  path: string;
  method: string | undefined;
  body: unknown;
}

function server(handlers: Record<string, (sent: Sent) => Response>) {
  const sent: Sent[] = [];
  const fetchImpl: FetchLike = (path, init) => {
    const entry: Sent = {
      path,
      method: init?.method,
      body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
    };
    sent.push(entry);
    const handler = handlers[`${init?.method ?? 'GET'} ${path}`];
    return Promise.resolve(handler ? handler(entry) : respond({}, 404));
  };
  return { fetchImpl, sent };
}

const contract = {
  required_inputs: ['question'],
  optional_inputs: [],
  guaranteed_outputs: ['draft_answer'],
  optional_outputs: [],
};

const catalogWire = {
  categories: ['other'],
  nodes: [
    {
      implementation_id: 'tunable',
      description: 'A configurable node.',
      category: 'other',
      recover_errors: false,
      contract,
      params: [
        { name: 'n', kind: 'integer', default: 2, required: false, minimum: 1, maximum: 9 },
        { name: 'mode', kind: 'enum', default: 'fast', required: false, choices: ['fast', 'slow'] },
        { name: 'label', kind: 'string', default: '', required: true, max_length: 8 },
        { name: 'must', kind: 'boolean', default: null, required: true },
      ],
    },
    {
      implementation_id: 'plain',
      description: 'No parameters.',
      category: 'other',
      recover_errors: false,
      contract,
    },
  ],
  routing_strategies: [],
  state: { types: ['AgentState'], fields: ['question'], initial_fields: ['question'] },
};

describe('the catalog and parameters', () => {
  it('reads each component parameter spec, with the limits that apply', async () => {
    const { fetchImpl } = server({ 'GET /api/catalog': () => respond(catalogWire) });
    const catalog = await createHttpServices(fetchImpl).catalog.getCatalog();
    const [tunable, plain] = catalog.components;
    expect(tunable?.params.map((p) => p.name)).toEqual(['n', 'mode', 'label', 'must']);
    expect(tunable?.params[0]).toEqual({
      name: 'n',
      kind: 'integer',
      default: 2,
      required: false,
      minimum: 1,
      maximum: 9,
      maxLength: null,
      choices: [],
    });
    expect(tunable?.params[1]?.choices).toEqual(['fast', 'slow']);
    expect(tunable?.params[2]).toMatchObject({ maxLength: 8, required: true });
    expect(tunable?.params[3]).toMatchObject({ default: null, required: true });
    expect(plain?.params).toEqual([]);
  });
});

const definitionWire = (params?: Record<string, unknown>) => ({
  schema_version: '4.0',
  architecture_id: 'tuned',
  state_type: 'AgentState',
  initial_node: 't',
  nodes: [
    { id: 't', implementation_id: 'tunable', description: '', ...(params ? { params } : {}) },
  ],
  edges: [{ source: 't', edge_type: 'direct', target: '__end__' }],
});

const record = (params?: Record<string, unknown>) => ({
  id: 'v1',
  architecture_id: 'tuned',
  version: 1,
  parent_id: null,
  content_sha256: 'a'.repeat(64),
  created_at: '2026-11-01T10:00:00Z',
  read_only: false,
  definition: definitionWire(params),
  validation: {
    is_valid: true,
    counts: { error: 0, warning: 0, info: 0 },
    diagnostics: [],
    availability: {},
  },
});

describe('a stored definition and parameters', () => {
  it('reads the values chosen on each node', async () => {
    const { fetchImpl } = server({
      'GET /api/architectures/v1': () => respond(record({ n: 4, mode: 'slow', flag: true })),
    });
    const architecture = await createHttpServices(fetchImpl).architectures.get('v1');
    expect(architecture.definition.nodes[0]?.params).toEqual({ n: 4, mode: 'slow', flag: true });
  });

  it('leaves params out when none were chosen', async () => {
    const { fetchImpl } = server({ 'GET /api/architectures/v1': () => respond(record()) });
    const architecture = await createHttpServices(fetchImpl).architectures.get('v1');
    expect(architecture.definition.nodes[0]).not.toHaveProperty('params');
  });

  it('refuses a stored value that is not plain JSON data', async () => {
    const { fetchImpl } = server({
      'GET /api/architectures/v1': () => respond(record({ n: { nested: 1 } })),
    });
    await expect(createHttpServices(fetchImpl).architectures.get('v1')).rejects.toMatchObject({
      kind: 'contract',
    });
  });

  it('sends params when saving, and only when there are some', async () => {
    const { fetchImpl, sent } = server({
      'GET /api/architectures': () => respond({ architectures: [] }),
      'POST /api/architectures': () => respond(record({ n: 4 })),
      'GET /api/architectures/v1': () => respond(record({ n: 4 })),
    });
    const definition: AgentDefinition = {
      schemaVersion: '4.0',
      architectureId: 'tuned',
      stateType: 'AgentState',
      initialNode: 't',
      nodes: [
        { id: 't', implementationId: 'tunable', description: '', params: { n: 4 } },
        { id: 'u', implementationId: 'plain', description: '' },
      ],
      edges: [],
    };
    await createHttpServices(fetchImpl).architectures.save(definition);
    const body = sent.find((entry) => entry.method === 'POST')?.body as {
      nodes: Record<string, unknown>[];
    };
    expect(body.nodes[0]).toMatchObject({ id: 't', params: { n: 4 } });
    expect(body.nodes[1]).not.toHaveProperty('params');
  });
});
