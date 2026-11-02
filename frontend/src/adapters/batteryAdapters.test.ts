import { describe, expect, it } from 'vitest';

import { IDLE_BATTERY } from '../domain/battery';
import { defaultSettings } from '../domain/experiment';
import { StudioError } from '../domain/errors';
import { createHttpServices, type FetchLike } from './http/httpServices';
import { createMemoryServices } from './memory/memoryServices';

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

const running = {
  state: 'running',
  experiment_id: 'e1',
  name: 'Studio',
  completed: 3,
  total: 20,
  started_at: '2026-11-01T10:00:00Z',
  error: null,
};

describe('batteries over HTTP', () => {
  it('starts a new battery with the settings, architecture and limit', async () => {
    const { fetchImpl, sent } = server({ 'POST /api/batteries': () => respond(running, 202) });
    const status = await createHttpServices(fetchImpl).batteries.start({
      kind: 'new',
      settings: defaultSettings(),
      architectureId: 'builtin:gaia_v31',
      limit: 5,
    });
    expect(status).toMatchObject({ state: 'running', experimentId: 'e1', completed: 3, total: 20 });
    expect(sent[0]?.body).toMatchObject({
      limit: 5,
      experiment: { architecture: 'builtin:gaia_v31', pipeline_version: '3.1' },
    });
  });

  it('resumes by experiment id only, so its own settings are kept', async () => {
    const { fetchImpl, sent } = server({ 'POST /api/batteries': () => respond(running, 202) });
    await createHttpServices(fetchImpl).batteries.start({ kind: 'resume', experimentId: 'e1' });
    expect(sent[0]?.body).toEqual({ resume_id: 'e1' });
  });

  it('reports a busy server as an http error with status 409', async () => {
    const { fetchImpl } = server({
      'POST /api/batteries': () => respond({ error: 'A battery is already running' }, 409),
    });
    const attempt = createHttpServices(fetchImpl).batteries.start({
      kind: 'resume',
      experimentId: 'e1',
    });
    await expect(attempt).rejects.toMatchObject({ kind: 'http', status: 409 });
  });

  it('reads the current battery and asks it to stop', async () => {
    const { fetchImpl, sent } = server({
      'GET /api/batteries/current': () => respond(running),
      'POST /api/batteries/stop': () => respond({ ...running, state: 'stopping' }),
    });
    const services = createHttpServices(fetchImpl);
    expect((await services.batteries.current()).state).toBe('running');
    expect((await services.batteries.stop()).state).toBe('stopping');
    expect(sent.at(-1)?.method).toBe('POST');
  });

  it('treats an idle server as an empty status', async () => {
    const { fetchImpl } = server({
      'GET /api/batteries/current': () => respond({ state: 'idle' }),
    });
    expect(await createHttpServices(fetchImpl).batteries.current()).toEqual(IDLE_BATTERY);
  });

  it('turns an unknown state into a failure instead of trusting it', async () => {
    const { fetchImpl } = server({
      'GET /api/batteries/current': () => respond({ state: 'exploding' }),
    });
    const status = await createHttpServices(fetchImpl).batteries.current();
    expect(status.state).toBe('failed');
    expect(status.error).toMatch(/exploding/);
  });
});

describe('experiment list', () => {
  it('summarizes stored records without needing their answers', async () => {
    const { fetchImpl } = server({
      'GET /api/experiments': () =>
        respond({
          experiments: [
            {
              id: 'a',
              status: 'cancelled',
              created_at: '2026-11-01T10:00:00Z',
              total_questions: 20,
              average_duration_seconds: 41.5,
              answers: [{ task_id: 't1' }, { task_id: 't2' }, { task_id: 't3' }],
              config: {
                name: 'V3.1 run',
                pipeline_version: '3.1',
                architecture: 'builtin:gaia_v31',
              },
            },
            {
              id: 'b',
              answers: Array.from({ length: 20 }, (_, n) => ({ task_id: `t${n}` })),
              config: { name: 'old', pipeline_version: '3.1' },
              local_score: { correct_count: 10, total_attempted: 20 },
            },
            { id: 'c', answers: [], config: { pipeline_version: 'weird' } },
          ],
        }),
    });
    const [a, b, c] = await createHttpServices(fetchImpl).experiments.list();
    expect(a).toMatchObject({
      id: 'a',
      status: 'cancelled',
      completed: 3,
      total: 20,
      pipelineVersion: '3.1',
      architecture: 'builtin:gaia_v31',
      averageSeconds: 41.5,
      localScore: null,
    });
    expect(b).toMatchObject({
      status: 'completed',
      total: 20,
      localScore: { correct: 10, attempted: 20, percent: 50 },
    });
    expect(c).toMatchObject({ name: 'c', pipelineVersion: null });
  });
});

describe('demo mode', () => {
  it('cannot start a battery, and lists nothing', async () => {
    const memory = createMemoryServices();
    await expect(
      memory.batteries.start({ kind: 'resume', experimentId: 'x' }),
    ).rejects.toBeInstanceOf(StudioError);
    expect(await memory.batteries.current()).toEqual(IDLE_BATTERY);
    expect(await memory.experiments.list()).toEqual([]);
  });
});
