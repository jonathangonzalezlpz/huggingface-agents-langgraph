import { describe, expect, it } from 'vitest';

import {
  canEvaluateLocally,
  canSubmitOfficially,
  filterHistory,
  sortHistory,
  submissionIssue,
  type ExperimentAnswer,
  type ExperimentRecord,
} from './history';

const answer = (n: number): ExperimentAnswer => ({
  taskId: `t${n}`,
  question: `q${n}`,
  fileName: '',
  answer: `a${n}`,
  error: '',
  route: 'direct',
  durationSeconds: 1,
  runId: null,
  locallyCorrect: null,
});

function record(over: Partial<ExperimentRecord> = {}): ExperimentRecord {
  return {
    id: 'a',
    status: 'completed',
    name: 'V3.1 base',
    pipelineVersion: '3.1',
    architecture: null,
    completed: 20,
    total: 20,
    createdAt: '2026-11-01T10:00:00Z',
    averageSeconds: 50,
    answers: Array.from({ length: 20 }, (_, n) => answer(n)),
    localScore: null,
    officialScore: null,
    ...over,
  };
}

describe('scoring availability', () => {
  it('needs all 20 answers', () => {
    expect(canEvaluateLocally(record())).toBe(true);
    expect(canEvaluateLocally(record({ answers: [answer(1)] }))).toBe(false);
  });

  it('offers the official evaluator only once per complete experiment', () => {
    expect(canSubmitOfficially(record())).toBe(true);
    expect(
      canSubmitOfficially(record({ officialScore: { percent: 45, correct: 9, attempted: 20 } })),
    ).toBe(false);
    expect(canSubmitOfficially(record({ answers: [answer(1)] }))).toBe(false);
  });
});

describe('sorting', () => {
  const old = record({ id: 'old', createdAt: '2026-10-01T00:00:00Z', averageSeconds: 30 });
  const fresh = record({
    id: 'fresh',
    createdAt: '2026-11-02T00:00:00Z',
    averageSeconds: 70,
    localScore: { percent: 50, correct: 10, attempted: 20 },
  });
  const unscored = record({ id: 'none', createdAt: '2026-10-15T00:00:00Z', averageSeconds: null });

  it('puts the newest first by default', () => {
    expect(sortHistory([old, fresh, unscored], 'newest').map((r) => r.id)).toEqual([
      'fresh',
      'none',
      'old',
    ]);
  });

  it('puts the best score first and unscored last', () => {
    expect(sortHistory([old, unscored, fresh], 'score')[0]?.id).toBe('fresh');
  });

  it('puts the fastest first and unknown times last', () => {
    expect(sortHistory([fresh, unscored, old], 'speed').map((r) => r.id)).toEqual([
      'old',
      'fresh',
      'none',
    ]);
  });

  it('does not change the list it is given', () => {
    const list = [old, fresh];
    sortHistory(list, 'score');
    expect(list.map((r) => r.id)).toEqual(['old', 'fresh']);
  });
});

describe('filtering', () => {
  it('matches name, architecture, version and status', () => {
    const list = [
      record({ id: '1', name: 'Alpha' }),
      record({ id: '2', name: 'Beta', architecture: 'custom-v2' }),
      record({ id: '3', name: 'Gamma', status: 'cancelled' }),
    ];
    expect(filterHistory(list, 'alp').map((r) => r.id)).toEqual(['1']);
    expect(filterHistory(list, 'custom').map((r) => r.id)).toEqual(['2']);
    expect(filterHistory(list, 'cancel').map((r) => r.id)).toEqual(['3']);
    expect(filterHistory(list, '  ')).toHaveLength(3);
  });
});

describe('official submission form', () => {
  it('needs a username and a code link', () => {
    expect(submissionIssue('', 'https://x')).toBe('username');
    expect(submissionIssue('me', '  ')).toBe('code');
    expect(submissionIssue('me', 'https://x')).toBeNull();
  });
});
