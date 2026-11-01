import { describe, expect, it } from 'vitest';

import { fromDefinition, toDefinition } from '../domain/editor/convert';
import { END, type EditorDocument } from '../domain/editor/model';
import { blankDocument, linearDocument } from '../domain/editor/templates';
import { createLocalStorageDrafts } from './drafts/localStorageDrafts';
import { createHttpServices, type FetchLike } from './http/httpServices';
import demo from './memory/demo-data.json';
import { createMemoryServices } from './memory/memoryServices';
import { definitionToWire } from './wire';

const memory = createMemoryServices();
const catalog = await memory.catalog.getCatalog();
const [summary] = await memory.architectures.list();
const builtin = await memory.architectures.get(summary?.id ?? '');

function respond(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('definition wire format', () => {
  it('serializes to exactly what the backend stored for the built-in pipeline', () => {
    expect(definitionToWire(builtin.definition)).toEqual({
      schema_version: demo.architecture.definition.schema_version,
      architecture_id: demo.architecture.definition.architecture_id,
      state_type: demo.architecture.definition.state_type,
      initial_node: demo.architecture.definition.initial_node,
      nodes: demo.architecture.definition.nodes.map((n) => ({
        id: n.id,
        implementation_id: n.implementation_id,
        description: n.description,
      })),
      edges: demo.architecture.definition.edges,
    });
  });

  it('survives the full editor round trip', () => {
    const { graph } = fromDefinition(builtin.definition, catalog);
    expect(definitionToWire(toDefinition(graph)).edges).toEqual(demo.architecture.definition.edges);
  });
});

describe('http validation and layout', () => {
  it('posts the definition in wire format and maps the report', async () => {
    let received: { path: string; method: string | undefined; body: unknown } | undefined;
    const services = createHttpServices((path, init) => {
      received = {
        path,
        method: init?.method,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      };
      return Promise.resolve(respond(demo.validation));
    });
    const report = await services.validation.validate(builtin.definition);
    expect(received?.path).toBe('/api/architectures/validate');
    expect(received?.method).toBe('POST');
    expect(received?.body).toHaveProperty('initial_node', 'preprocessing');
    expect(report.isValid).toBe(true);
    expect(report.counts.warning).toBe(4);
  });

  it('reads and stores a layout through the version-specific endpoint', async () => {
    const calls: { path: string; method: string | undefined; body: unknown }[] = [];
    const services = createHttpServices((path, init) => {
      calls.push({
        path,
        method: init?.method,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      });
      return Promise.resolve(
        respond({
          architecture_version_id: 'builtin:gaia_v31',
          layout: { nodes: { router: { x: 1, y: 2 } } },
          updated_at: null,
        }),
      );
    });
    expect(await services.layouts.get('builtin:gaia_v31')).toEqual({ router: { x: 1, y: 2 } });
    await services.layouts.save('builtin:gaia_v31', { router: { x: 3, y: 4 } });
    expect(calls[0]?.path).toBe('/api/architectures/builtin%3Agaia_v31/layout');
    expect(calls[1]).toMatchObject({
      path: '/api/architectures/builtin%3Agaia_v31/layout',
      method: 'PUT',
      body: { nodes: { router: { x: 3, y: 4 } } },
    });
  });

  it('surfaces validation failures as typed errors', async () => {
    const fetchImpl: FetchLike = () => Promise.resolve(respond({ error: 'bad' }, 400));
    await expect(
      createHttpServices(fetchImpl).validation.validate(builtin.definition),
    ).rejects.toMatchObject({ kind: 'http', status: 400 });
  });
});

describe('demo mode validation', () => {
  it('knows the report of the built-in pipeline only', async () => {
    expect((await memory.validation.validate(builtin.definition)).isValid).toBe(true);
    const edited = { ...builtin.definition, architectureId: 'edited' };
    await expect(memory.validation.validate(edited)).rejects.toMatchObject({
      kind: 'unavailable',
    });
  });

  it('keeps layouts in memory', async () => {
    const services = createMemoryServices();
    expect(await services.layouts.get('x')).toEqual({});
    await services.layouts.save('x', { a: { x: 1, y: 2 } });
    expect(await services.layouts.get('x')).toEqual({ a: { x: 1, y: 2 } });
  });
});

function fakeStorage(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial));
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, value),
  };
}

describe('local drafts', () => {
  const doc: EditorDocument = linearDocument('mine', catalog);

  it('saves, lists, loads and removes drafts', () => {
    const drafts = createLocalStorageDrafts(fakeStorage(), () => 1000);
    drafts.save('d1', doc);
    drafts.save('d2', blankDocument('other'));
    expect(
      drafts
        .list()
        .map((d) => d.id)
        .sort(),
    ).toEqual(['d1', 'd2']);
    expect(drafts.list().find((d) => d.id === 'd1')).toMatchObject({
      architectureId: 'mine',
      nodeCount: 3,
      updatedAt: 1000,
    });
    expect(drafts.load('d1')).toEqual(doc);
    drafts.remove('d1');
    expect(drafts.load('d1')).toBeNull();
  });

  it('lists the most recently edited draft first', () => {
    let now = 1;
    const drafts = createLocalStorageDrafts(fakeStorage(), () => now);
    drafts.save('old', doc);
    now = 5;
    drafts.save('new', doc);
    expect(drafts.list().map((d) => d.id)).toEqual(['new', 'old']);
  });

  it('ignores corrupt or outdated stored data instead of failing', () => {
    for (const bad of ['not json', '{"version":99}', '[1,2]', '{"version":1,"drafts":"x"}']) {
      const drafts = createLocalStorageDrafts(fakeStorage({ 'studio.drafts.v1': bad }));
      expect(drafts.list()).toEqual([]);
      expect(drafts.load('d1')).toBeNull();
      drafts.save('d1', doc);
      expect(drafts.load('d1')).toEqual(doc);
    }
  });

  it('drops a stored draft whose document breaks the model rules', () => {
    const broken = structuredClone(doc);
    broken.graph.initialNode = 'ghost';
    const stored = JSON.stringify({
      version: 1,
      drafts: [{ id: 'd1', updatedAt: 1, document: broken }],
    });
    const drafts = createLocalStorageDrafts(fakeStorage({ 'studio.drafts.v1': stored }));
    expect(drafts.load('d1')).toBeNull();
    expect(drafts.list()).toEqual([]);
  });

  it('keeps only a bounded number of drafts', () => {
    let now = 0;
    const drafts = createLocalStorageDrafts(fakeStorage(), () => (now += 1));
    for (let i = 0; i < 30; i += 1) drafts.save(`d${i}`, doc);
    expect(drafts.list()).toHaveLength(20);
    expect(drafts.load('d29')).not.toBeNull();
    expect(drafts.load('d0')).toBeNull();
  });

  it('survives a storage that refuses writes', () => {
    const storage = fakeStorage();
    storage.setItem = () => {
      throw new DOMException('quota', 'QuotaExceededError');
    };
    const drafts = createLocalStorageDrafts(storage);
    expect(() => drafts.save('d1', doc)).not.toThrow();
  });

  it('never stores the end marker as a node', () => {
    const drafts = createLocalStorageDrafts(fakeStorage());
    drafts.save('d1', doc);
    expect(drafts.load('d1')?.graph.nodes.some((n) => n.id === END)).toBe(false);
  });
});
