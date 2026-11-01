import { describe, expect, it } from 'vitest';

import { StudioError } from '../domain/errors';
import { createHttpServices, type FetchLike } from './http/httpServices';
import demo from './memory/demo-data.json';
import { createMemoryServices } from './memory/memoryServices';

const summary = Object.fromEntries(
  Object.entries(demo.architecture).filter(([key]) => key !== 'definition'),
);
const detail = { ...demo.architecture, validation: demo.validation };

function respond(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function serving(routes: Record<string, () => Response>): FetchLike {
  return (input) => {
    const route = routes[input];
    return route ? Promise.resolve(route()) : Promise.resolve(respond({}, 404));
  };
}

describe('http adapter', () => {
  it('maps the catalog to the domain model', async () => {
    const services = createHttpServices(serving({ '/api/catalog': () => respond(demo.catalog) }));
    const catalog = await services.catalog.getCatalog();
    expect(catalog.components).toHaveLength(12);
    const web = catalog.components.find((c) => c.implementationId === 'web_research');
    expect(web).toMatchObject({ category: 'acquisition', recoverErrors: true });
    expect(web?.contract.requiredInputs).toEqual(['question']);
    expect(catalog.routingStrategies.map((s) => s.identifier)).toContain('route_after_review');
  });

  it('lists architectures and maps summaries', async () => {
    const services = createHttpServices(
      serving({ '/api/architectures': () => respond({ architectures: [summary] }) }),
    );
    const [item] = await services.architectures.list();
    expect(item).toMatchObject({
      id: 'builtin:gaia_v31',
      architectureId: 'gaia_v31',
      version: null,
      readOnly: true,
    });
  });

  it('encodes ids and maps definitions, edges and validation', async () => {
    const requested: string[] = [];
    const services = createHttpServices((input) => {
      requested.push(input);
      return Promise.resolve(respond(detail));
    });
    const architecture = await services.architectures.get('builtin:gaia_v31');
    expect(requested).toEqual(['/api/architectures/builtin%3Agaia_v31']);
    expect(architecture.definition.nodes).toHaveLength(12);
    const conditional = architecture.definition.edges.filter((e) => e.type === 'conditional');
    expect(conditional).toHaveLength(3);
    expect(architecture.validation.isValid).toBe(true);
    expect(architecture.validation.counts.warning).toBe(4);
    expect(architecture.validation.diagnostics[0]).toHaveProperty('severity');
  });

  it('reports http errors with their status', async () => {
    const services = createHttpServices(serving({}));
    await expect(services.catalog.getCatalog()).rejects.toMatchObject({
      kind: 'http',
      status: 404,
    });
  });

  it('reports unreachable backends as network errors', async () => {
    const services = createHttpServices(() => Promise.reject(new TypeError('Failed to fetch')));
    await expect(services.architectures.list()).rejects.toMatchObject({ kind: 'network' });
  });

  it('rejects responses that break the contract', async () => {
    const services = createHttpServices(
      serving({ '/api/catalog': () => respond({ nodes: 'nope' }) }),
    );
    const failure = await services.catalog.getCatalog().catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(StudioError);
    expect(failure).toMatchObject({ kind: 'contract' });
  });

  it('rejects bodies that are not JSON', async () => {
    const services = createHttpServices(() =>
      Promise.resolve(new Response('<html>', { status: 200 })),
    );
    await expect(services.catalog.getCatalog()).rejects.toMatchObject({ kind: 'contract' });
  });

  describe('system status', () => {
    it('reads the model state', async () => {
      const services = createHttpServices(
        serving({ '/api/status': () => respond({ llm: { state: 'sleeping', name: 'LLM' } }) }),
      );
      expect(await services.system.getStatus()).toEqual({
        backend: 'online',
        llm: { state: 'sleeping', name: 'LLM' },
        gpu: null,
        hostMemory: null,
      });
    });

    it('treats unknown model states as unavailable', async () => {
      const services = createHttpServices(
        serving({ '/api/status': () => respond({ llm: { state: 'exploding', name: 'LLM' } }) }),
      );
      expect((await services.system.getStatus()).llm?.state).toBe('unavailable');
    });

    it('reads the graphics card and the host memory when the backend reports them', async () => {
      const services = createHttpServices(
        serving({
          '/api/status': () =>
            respond({
              llm: { state: 'ready', name: 'LLM' },
              gpu: { available: true, name: 'NVIDIA GeForce RTX 4060 Ti', backend: 'CUDA' },
              host_memory: { available_mib: 3796, total_mib: 16197 },
            }),
        }),
      );
      const status = await services.system.getStatus();
      expect(status.gpu).toEqual({
        available: true,
        name: 'NVIDIA GeForce RTX 4060 Ti',
        backend: 'CUDA',
      });
      expect(status.hostMemory).toEqual({ availableMib: 3796, totalMib: 16197 });
    });

    it('reports no graphics card as unavailable, not as unknown', async () => {
      const services = createHttpServices(
        serving({ '/api/status': () => respond({ gpu: { available: false } }) }),
      );
      expect((await services.system.getStatus()).gpu).toEqual({
        available: false,
        name: null,
        backend: null,
      });
    });

    it('reports an unreachable backend as offline instead of failing', async () => {
      const services = createHttpServices(() => Promise.reject(new TypeError('down')));
      expect(await services.system.getStatus()).toEqual({
        backend: 'offline',
        llm: null,
        gpu: null,
        hostMemory: null,
      });
    });

    it('keeps the backend online when only the status call fails', async () => {
      const services = createHttpServices(serving({ '/api/status': () => respond({}, 500) }));
      expect(await services.system.getStatus()).toEqual({
        backend: 'online',
        llm: null,
        gpu: null,
        hostMemory: null,
      });
    });
  });
});

describe('memory adapter', () => {
  it('serves the built-in pipeline in demo mode', async () => {
    const services = createMemoryServices();
    expect(services.mode).toBe('demo');
    const [item] = await services.architectures.list();
    expect(item?.readOnly).toBe(true);
    const architecture = await services.architectures.get(item?.id ?? '');
    expect(architecture.definition.initialNode).toBe('preprocessing');
    expect(architecture.validation.isValid).toBe(true);
  });

  it('rejects unknown architectures like the real backend', async () => {
    await expect(createMemoryServices().architectures.get('nope')).rejects.toMatchObject({
      kind: 'http',
      status: 404,
    });
  });

  it('serves the same catalog the backend exposes', async () => {
    const catalog = await createMemoryServices().catalog.getCatalog();
    expect(catalog.components).toHaveLength(12);
    expect(catalog.state.initialFields).toEqual(['file_name', 'question', 'task_id']);
  });

  it('contains no benchmark questions, answers or run records', () => {
    expect(Object.keys(demo)).toEqual(['catalog', 'architecture', 'validation']);
  });
});
