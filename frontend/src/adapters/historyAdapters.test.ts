import { describe, expect, it } from 'vitest';

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

describe('stored experiments', () => {
  it('maps each answer, including the local and official scores', async () => {
    const { fetchImpl } = server({
      'GET /api/experiments': () =>
        respond({
          experiments: [
            {
              id: 'a',
              answers: [
                {
                  task_id: 't1',
                  question: 'What?',
                  file_name: null,
                  submitted_answer: '42',
                  error: '',
                  route: 'direct',
                  duration_seconds: 3.5,
                  run_id: 'r1',
                  locally_correct: true,
                },
                { task_id: 't2', submitted_answer: null, error: 'boom' },
              ],
              local_score: { score: 50, correct_count: 1, total_attempted: 2 },
              score: { score: 45, correct_count: 9, total_attempted: 20 },
            },
          ],
        }),
    });
    const [record] = await createHttpServices(fetchImpl).experiments.list();
    expect(record?.answers[0]).toEqual({
      taskId: 't1',
      question: 'What?',
      fileName: '',
      answer: '42',
      error: '',
      route: 'direct',
      durationSeconds: 3.5,
      runId: 'r1',
      locallyCorrect: true,
    });
    expect(record?.answers[1]).toMatchObject({ answer: '', error: 'boom', locallyCorrect: null });
    expect(record?.localScore).toEqual({ percent: 50, correct: 1, attempted: 2 });
    expect(record?.officialScore).toEqual({ percent: 45, correct: 9, attempted: 20 });
  });

  it('deletes by id', async () => {
    const { fetchImpl, sent } = server({
      'DELETE /api/experiments/a%2Fb': () => respond({ deleted: true }),
    });
    await createHttpServices(fetchImpl).experiments.remove('a/b');
    expect(sent[0]?.method).toBe('DELETE');
  });

  it('asks the server to score locally and returns the score', async () => {
    const { fetchImpl, sent } = server({
      'POST /api/experiments/a/evaluate': () =>
        respond({ score: 40, correct_count: 8, total_attempted: 20 }),
    });
    const score = await createHttpServices(fetchImpl).experiments.evaluate('a');
    expect(score).toEqual({ percent: 40, correct: 8, attempted: 20 });
    expect(sent[0]?.body).toBeUndefined();
  });

  it('rejects an evaluation the server refuses', async () => {
    const { fetchImpl } = server({
      'POST /api/experiments/a/evaluate': () => respond({ error: 'Exactly 20' }, 400),
    });
    await expect(createHttpServices(fetchImpl).experiments.evaluate('a')).rejects.toMatchObject({
      kind: 'http',
      status: 400,
    });
  });
});

describe('official submission', () => {
  it('sends only the experiment id, the user name and the code link', async () => {
    const { fetchImpl, sent } = server({
      'POST /api/score': () =>
        respond({ score: 45, correct_count: 9, total_attempted: 20, saved: true }),
    });
    const result = await createHttpServices(fetchImpl).experiments.submitOfficial({
      experimentId: 'a',
      username: 'someone',
      agentCode: 'https://code',
    });
    expect(sent[0]?.body).toEqual({
      experiment_id: 'a',
      username: 'someone',
      agent_code: 'https://code',
    });
    expect(result).toEqual({ score: { percent: 45, correct: 9, attempted: 20 }, saved: true });
  });

  it('reports that the verdict was received but not stored', async () => {
    const { fetchImpl } = server({
      'POST /api/score': () =>
        respond({ score: 45, correct_count: 9, total_attempted: 20, saved: false }),
    });
    const result = await createHttpServices(fetchImpl).experiments.submitOfficial({
      experimentId: 'a',
      username: 'u',
      agentCode: 'c',
    });
    expect(result.saved).toBe(false);
  });

  it('surfaces an unreachable evaluator as an http error', async () => {
    const { fetchImpl } = server({
      'POST /api/score': () => respond({ error: 'Official scoring failed' }, 502),
    });
    await expect(
      createHttpServices(fetchImpl).experiments.submitOfficial({
        experimentId: 'a',
        username: 'u',
        agentCode: 'c',
      }),
    ).rejects.toMatchObject({ kind: 'http', status: 502 });
  });
});

const comparisonWire = {
  base_group: 'g1',
  experiments: [
    {
      id: 'a',
      name: 'A',
      status: 'completed',
      group: 'g1',
      metrics: {
        answered: 20,
        correct: 9,
        accuracy: 0.45,
        mean_seconds: 45.9,
        median_seconds: 40,
        p95_seconds: 86,
        technical_errors: 2,
        truncated_calls: 4,
      },
    },
    {
      id: 'b',
      group: 'g2',
      metrics: { answered: 20, correct: null, accuracy: null },
    },
  ],
  groups: [
    {
      key: 'g1',
      experiment_ids: ['a'],
      runs: 1,
      accuracy: { min: 0.45, max: 0.45, mean: 0.45 },
      mean_seconds: { min: 45.9, max: 45.9, mean: 45.9 },
      versus_base: null,
    },
    {
      key: 'g2',
      experiment_ids: ['b'],
      runs: 1,
      accuracy: null,
      mean_seconds: null,
      versus_base: {
        gained: 1,
        lost: 2,
        unchanged: 15,
        unknown: 2,
        accuracy_difference: { delta: -0.05, assessment: 'not_assessable' },
        mean_seconds_delta: 3.5,
      },
    },
  ],
  comparability: {
    same_task_set: true,
    same_code: null,
    same_architecture: true,
    config_differences: { model: { a: {}, b: {} }, seed: { a: 1, b: 2 } },
    warnings: ['Code identity is unknown for some experiments.'],
  },
  tasks: [
    {
      task_id: 't1',
      outcomes: {
        a: { correct: true, route: 'direct', seconds: 3, error: false, versus_base: null },
        b: { correct: false, route: null, seconds: null, error: true, versus_base: 'lost' },
      },
    },
  ],
};

describe('comparison', () => {
  it('posts ids and base, and maps the result', async () => {
    const { fetchImpl, sent } = server({
      'POST /api/experiments/compare': () => respond(comparisonWire),
    });
    const result = await createHttpServices(fetchImpl).experiments.compare({
      ids: ['a', 'b'],
      base: 'a',
    });
    expect(sent[0]?.body).toEqual({ ids: ['a', 'b'], base: 'a' });
    expect(result.baseGroup).toBe('g1');
    expect(result.experiments[1]).toMatchObject({
      name: 'b',
      status: 'completed',
      metrics: { accuracy: null, technicalErrors: 0 },
    });
    expect(result.groups[1]?.versusBase).toMatchObject({
      gained: 1,
      lost: 2,
      accuracyDelta: -0.05,
      assessment: 'not_assessable',
      meanSecondsDelta: 3.5,
    });
    expect(result.comparability).toMatchObject({
      sameCode: null,
      configDifferences: ['model', 'seed'],
    });
    expect(result.tasks[0]?.outcomes.b).toMatchObject({ correct: false, versusBase: 'lost' });
  });

  it('leaves the base out when none is chosen', async () => {
    const { fetchImpl, sent } = server({
      'POST /api/experiments/compare': () => respond(comparisonWire),
    });
    await createHttpServices(fetchImpl).experiments.compare({ ids: ['a', 'b'], base: null });
    expect(sent[0]?.body).toEqual({ ids: ['a', 'b'] });
  });

  it('rejects a response that does not look like a comparison', async () => {
    const { fetchImpl } = server({ 'POST /api/experiments/compare': () => respond({ nope: 1 }) });
    await expect(
      createHttpServices(fetchImpl).experiments.compare({ ids: ['a', 'b'], base: null }),
    ).rejects.toMatchObject({ kind: 'contract' });
  });
});

describe('demo mode', () => {
  it('cannot delete, score or compare', async () => {
    const { experiments } = createMemoryServices();
    await expect(experiments.remove('a')).rejects.toMatchObject({ kind: 'unavailable' });
    await expect(experiments.evaluate('a')).rejects.toMatchObject({ kind: 'unavailable' });
    await expect(
      experiments.submitOfficial({ experimentId: 'a', username: 'u', agentCode: 'c' }),
    ).rejects.toMatchObject({ kind: 'unavailable' });
    await expect(experiments.compare({ ids: ['a', 'b'], base: null })).rejects.toMatchObject({
      kind: 'unavailable',
    });
  });
});
