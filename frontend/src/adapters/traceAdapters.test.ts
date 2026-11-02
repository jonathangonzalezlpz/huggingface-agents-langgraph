import { describe, expect, it } from 'vitest';

import { createHttpServices, type FetchLike } from './http/httpServices';
import { createMemoryServices } from './memory/memoryServices';

function respond(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function server(routes: Record<string, unknown>): { fetchImpl: FetchLike; paths: string[] } {
  const paths: string[] = [];
  const fetchImpl: FetchLike = (path) => {
    paths.push(path);
    return Promise.resolve(path in routes ? respond(routes[path]) : respond({}, 404));
  };
  return { fetchImpl, paths };
}

const wireTrace = {
  trace_id: 'run-1',
  spans: [
    {
      span_id: 'a',
      parent_id: null,
      kind: 'run',
      name: 'run',
      status: 'ok',
      start_offset_seconds: 0,
      duration_seconds: 3,
      attributes: {},
    },
    {
      span_id: 'b',
      parent_id: 'a',
      kind: 'node',
      name: 'search',
      status: 'error',
      start_offset_seconds: 0,
      duration_seconds: 1,
      attributes: { updated_fields: ['evidence', 'source_links'] },
      error: 'boom',
    },
    {
      span_id: 'c',
      parent_id: 'b',
      kind: 'llm',
      name: 'llm_call',
      status: 'ok',
      start_offset_seconds: 0.2,
      duration_seconds: 0.5,
      attributes: { prompt_tokens: 10, linked_to_node: true, model: 'm' },
    },
  ],
  summary: {
    status: 'completed',
    duration_seconds: 3,
    node_count: 1,
    llm_calls: 1,
    prompt_tokens: 10,
    completion_tokens: 3,
    error_count: 1,
    unsupported_figures: ['568'],
    slowest_node: { name: 'search', duration_seconds: 1 },
  },
};

const wireInsights = {
  totals: {
    answered: 4,
    scored: 4,
    correct: 2,
    accuracy: 0.5,
    mean_seconds: 14,
    completion_tokens: 50,
    technical_errors: 1,
  },
  routes: [{ route: 'web', count: 3, scored: 3, correct: 1, accuracy: 0.3333, mean_seconds: 12 }],
  stages: [{ stage: 'review', total_seconds: 48, mean_seconds: 12, tasks: 4, share: 0.6 }],
  failures: {
    wrong_answers: 1,
    errors: [{ message: 'truncated', count: 1 }],
    truncated_calls: 1,
  },
  tasks: [{ task_id: 't1', outcome: 'correct' }],
  slowest_tasks: [{ task_id: 't2', duration_seconds: 30, slowest_stage: 'review' }],
};

describe('traces', () => {
  it('reads a trace and maps spans to the domain, flattening list attributes', async () => {
    const { fetchImpl, paths } = server({ '/api/runs/run-1/trace': wireTrace });

    const trace = await createHttpServices(fetchImpl).traces.getTrace('run-1');

    expect(paths).toEqual(['/api/runs/run-1/trace']);
    expect(trace.id).toBe('run-1');
    expect(trace.spans[1]).toMatchObject({
      id: 'b',
      parentId: 'a',
      kind: 'node',
      status: 'error',
      error: 'boom',
      startSeconds: 0,
      durationSeconds: 1,
      attributes: { updated_fields: 'evidence, source_links' },
    });
    expect(trace.spans[0]?.error).toBeNull();
    expect(trace.spans[2]?.attributes).toEqual({
      prompt_tokens: 10,
      linked_to_node: true,
      model: 'm',
    });
    expect(trace.summary).toMatchObject({
      durationSeconds: 3,
      llmCalls: 1,
      promptTokens: 10,
      errorCount: 1,
      unsupportedFigures: ['568'],
      slowestNode: { name: 'search', durationSeconds: 1 },
    });
  });

  it('keeps reading a trace whose attributes are not scalars', async () => {
    const odd = {
      ...wireTrace,
      spans: wireTrace.spans.map((item, index) =>
        index === 2
          ? {
              ...item,
              attributes: { model: { provider: 'configured', model_id: 'm' }, thinking: true },
            }
          : item,
      ),
    };
    const { fetchImpl } = server({ '/api/runs/run-1/trace': odd });

    const trace = await createHttpServices(fetchImpl).traces.getTrace('run-1');

    expect(trace.spans[2]?.attributes).toEqual({
      model: '{"provider":"configured","model_id":"m"}',
      thinking: true,
    });
  });

  it('loads the payload of a span on demand', async () => {
    const { fetchImpl } = server({ '/api/runs/run-1/spans/b': { update: { k: 1 } } });

    const payload = await createHttpServices(fetchImpl).traces.getSpanPayload('run-1', 'b');

    expect(payload).toEqual({ update: { k: 1 } });
  });

  it('rejects a trace with an unexpected shape as a contract error', async () => {
    const { fetchImpl } = server({ '/api/runs/run-1/trace': { spans: 'nope' } });

    await expect(createHttpServices(fetchImpl).traces.getTrace('run-1')).rejects.toMatchObject({
      kind: 'contract',
    });
  });

  it('reads the insights of a battery', async () => {
    const { fetchImpl } = server({ '/api/experiments/e1/insights': wireInsights });

    const insights = await createHttpServices(fetchImpl).traces.getInsights('e1');

    expect(insights.totals).toMatchObject({ answered: 4, accuracy: 0.5, meanSeconds: 14 });
    expect(insights.routes[0]).toMatchObject({ route: 'web', count: 3, accuracy: 0.3333 });
    expect(insights.stages[0]).toMatchObject({ stage: 'review', totalSeconds: 48, share: 0.6 });
    expect(insights.failures).toEqual({
      wrongAnswers: 1,
      errors: [{ message: 'truncated', count: 1 }],
      truncatedCalls: 1,
    });
    expect(insights.slowestTasks[0]).toEqual({
      taskId: 't2',
      durationSeconds: 30,
      slowestStage: 'review',
    });
  });

  it('is unavailable in the demo, which has no stored runs', async () => {
    const services = createMemoryServices();

    await expect(services.traces.getTrace('x')).rejects.toMatchObject({ kind: 'unavailable' });
    await expect(services.traces.getInsights('x')).rejects.toMatchObject({
      kind: 'unavailable',
    });
  });
});
