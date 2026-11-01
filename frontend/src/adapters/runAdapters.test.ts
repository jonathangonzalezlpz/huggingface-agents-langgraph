import { describe, expect, it } from 'vitest';

import { defaultSettings } from '../domain/experiment';
import type { RunRequest } from '../domain/run';
import { createHttpServices, type FetchLike } from './http/httpServices';
import { createMemoryServices } from './memory/memoryServices';

function respond(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const request: RunRequest = {
  architectureId: 'builtin:gaia_v31',
  question: 'What is 2+2?',
  taskId: 'studio-1',
  fileName: '',
  settings: defaultSettings(),
};

const record = {
  id: 'run-1',
  status: 'completed',
  duration_seconds: 12.5,
  steps: [
    { node: 'preprocessing', duration_seconds: 0.1, update: { question: 'x' } },
    { node: 'router', duration_seconds: 2, update: { route: 'direct' } },
    { node: 'reasoning', duration_seconds: 9, update: { draft_answer: '4', research_notes: [] } },
  ],
  architecture: {
    engine: 'compiled',
    id: 'builtin:gaia_v31',
    version: null,
    content_sha256: 'e42d',
  },
  task: { question: 'What is 2+2?', experiment: { model: { provider: 'ollama', model_id: 'm1' } } },
  result: { submitted_answer: '4', route: 'direct' },
};

interface Sent {
  path: string;
  method: string | undefined;
  body: unknown;
  signal: AbortSignal | null | undefined;
}

function server(handlers: Record<string, (sent: Sent) => Response>): {
  fetchImpl: FetchLike;
  sent: Sent[];
} {
  const sent: Sent[] = [];
  const fetchImpl: FetchLike = (path, init) => {
    const entry: Sent = {
      path,
      method: init?.method,
      body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      signal: init?.signal,
    };
    sent.push(entry);
    const handler = handlers[`${init?.method ?? 'GET'} ${path}`];
    return Promise.resolve(handler ? handler(entry) : respond({}, 404));
  };
  return { fetchImpl, sent };
}

describe('running an architecture', () => {
  it('posts the run, then reads the record and maps it to the domain', async () => {
    const { fetchImpl, sent } = server({
      'POST /api/run': () => respond({ run_id: 'run-1', submitted_answer: '4' }),
      'GET /api/runs/run-1': () => respond(record),
    });
    const result = await createHttpServices(fetchImpl).runs.run(request);
    expect(result).toMatchObject({
      id: 'run-1',
      status: 'completed',
      durationSeconds: 12.5,
      answer: '4',
      route: 'direct',
      question: 'What is 2+2?',
      modelId: 'm1',
      architecture: { engine: 'compiled', id: 'builtin:gaia_v31', version: null },
    });
    expect(result.steps.map((s) => s.node)).toEqual(['preprocessing', 'router', 'reasoning']);
    expect(result.steps[2]).toMatchObject({
      durationSeconds: 9,
      error: null,
      updatedFields: ['draft_answer', 'research_notes'],
    });
    const post = sent.find((s) => s.method === 'POST');
    expect(post?.body).toMatchObject({
      task_id: 'studio-1',
      question: 'What is 2+2?',
      file_name: '',
      experiment: { architecture: 'builtin:gaia_v31', pipeline_version: '3.1' },
    });
    expect(post?.body).not.toHaveProperty('experiment.model');
  });

  it('asks for the chosen model and passes the attachment name', async () => {
    const { fetchImpl, sent } = server({
      'POST /api/run': () => respond({ run_id: 'run-1' }),
      'GET /api/runs/run-1': () => respond(record),
    });
    await createHttpServices(fetchImpl).runs.run({
      ...request,
      fileName: 'data.xlsx',
      settings: { ...defaultSettings(), model: { provider: 'ollama', modelId: 'qwen2' } },
    });
    expect(sent[0]?.body).toMatchObject({
      file_name: 'data.xlsx',
      experiment: { model: { provider: 'ollama', model_id: 'qwen2' } },
    });
  });

  it('returns a failed run as a record instead of throwing, so the failure can be shown', async () => {
    const failed = {
      ...record,
      status: 'error',
      error: 'LLM output was truncated by the token limit',
      steps: [
        { node: 'preprocessing', duration_seconds: 0.1, update: {} },
        { node: 'review', duration_seconds: 20, error: 'truncated' },
      ],
      result: undefined,
    };
    const { fetchImpl } = server({
      'POST /api/run': () => respond({ error: 'truncated', run_id: 'run-1' }, 400),
      'GET /api/runs/run-1': () => respond(failed),
    });
    const result = await createHttpServices(fetchImpl).runs.run(request);
    expect(result.status).toBe('error');
    expect(result.error).toBe('LLM output was truncated by the token limit');
    expect(result.answer).toBeNull();
    expect(result.steps.at(-1)).toMatchObject({ node: 'review', error: 'truncated' });
  });

  it('throws with the backend message when the run was refused before it started', async () => {
    const { fetchImpl } = server({
      'POST /api/run': () => respond({ error: 'question is required' }, 400),
    });
    await expect(createHttpServices(fetchImpl).runs.run(request)).rejects.toMatchObject({
      kind: 'http',
      status: 400,
      message: expect.stringContaining('question is required'),
    });
  });

  it('reports an unreachable backend as a network error', async () => {
    const failing: FetchLike = () => Promise.reject(new TypeError('Failed to fetch'));
    await expect(createHttpServices(failing).runs.run(request)).rejects.toMatchObject({
      kind: 'network',
    });
  });

  it('reports a cancelled wait as aborted and forwards the signal', async () => {
    const controller = new AbortController();
    const { fetchImpl, sent } = server({
      'POST /api/run': () => respond({ run_id: 'run-1' }),
      'GET /api/runs/run-1': () => respond(record),
    });
    await createHttpServices(fetchImpl).runs.run(request, controller.signal);
    expect(sent[0]?.signal).toBe(controller.signal);

    const aborting: FetchLike = () => Promise.reject(new DOMException('stop', 'AbortError'));
    await expect(createHttpServices(aborting).runs.run(request)).rejects.toMatchObject({
      kind: 'aborted',
    });
  });

  it('reads a stored run by id and rejects a response that is not a record', async () => {
    const good = server({ 'GET /api/runs/run-1': () => respond(record) });
    expect((await createHttpServices(good.fetchImpl).runs.get('run-1')).id).toBe('run-1');
    const bad = server({ 'GET /api/runs/run-1': () => respond({ nope: true }) });
    await expect(createHttpServices(bad.fetchImpl).runs.get('run-1')).rejects.toMatchObject({
      kind: 'contract',
    });
  });
});

describe('models and questions', () => {
  it('lists available models and ignores providers it does not know', async () => {
    const { fetchImpl } = server({
      'GET /api/models': () =>
        respond({
          models: [
            { provider: 'ollama', model_id: 'qwen2:latest' },
            { provider: 'configured', model_id: 'Qwen3-8B' },
            { provider: 'other', model_id: 'ignored' },
          ],
          vision_models: [
            { provider: 'configured', model_id: 'Qwen-VL' },
            { provider: 'other', model_id: 'ignored' },
          ],
        }),
    });
    expect(await createHttpServices(fetchImpl).models.list()).toEqual({
      models: [
        { provider: 'ollama', modelId: 'qwen2:latest' },
        { provider: 'configured', modelId: 'Qwen3-8B' },
      ],
      visionModels: [{ provider: 'configured', modelId: 'Qwen-VL' }],
    });
  });

  it('lists GAIA questions with their attachment and level', async () => {
    const { fetchImpl } = server({
      'GET /api/questions': () =>
        respond([
          { task_id: 't1', question: 'Q one', Level: '1', file_name: 'a.py' },
          { task_id: 't2', question: 'Q two', Level: 2, file_name: null },
        ]),
    });
    expect(await createHttpServices(fetchImpl).questions.list()).toEqual([
      { taskId: 't1', question: 'Q one', level: '1', fileName: 'a.py' },
      { taskId: 't2', question: 'Q two', level: '2', fileName: '' },
    ]);
  });

  it('reports the course service being down as an http error', async () => {
    const { fetchImpl } = server({
      'GET /api/questions': () => respond({ error: 'Could not fetch questions' }, 502),
    });
    await expect(createHttpServices(fetchImpl).questions.list()).rejects.toMatchObject({
      kind: 'http',
      status: 502,
    });
  });
});

describe('demo mode', () => {
  const memory = createMemoryServices();

  it('cannot run, and never offers benchmark questions', async () => {
    await expect(memory.runs.run(request)).rejects.toMatchObject({ kind: 'unavailable' });
    await expect(memory.questions.list()).rejects.toMatchObject({ kind: 'unavailable' });
  });

  it('has no models and no stored runs', async () => {
    expect(await memory.models.list()).toEqual({ models: [], visionModels: [] });
    await expect(memory.runs.get('x')).rejects.toMatchObject({ kind: 'http', status: 404 });
  });
});
