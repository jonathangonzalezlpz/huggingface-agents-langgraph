import { describe, expect, it } from 'vitest';

import { END } from './editor/model';
import { failedStep, traversedEdges, visitsByNode } from './runPath';
import type { RunStep } from './run';

const step = (node: string, seconds = 1, error: string | null = null): RunStep => ({
  node,
  durationSeconds: seconds,
  error,
  updatedFields: [],
});

const PIPELINE = [
  step('preprocessing', 0.1),
  step('router', 2),
  step('review', 3),
  step('research_action', 5),
  step('review', 4),
  step('reasoning', 6),
  step('answer_production', 1),
];

describe('visitsByNode', () => {
  it('counts visits and adds up time, so a loop shows as repeated work', () => {
    const visits = visitsByNode(PIPELINE);
    expect(visits.get('review')).toMatchObject({ visits: 2, seconds: 7, failed: false });
    expect(visits.get('router')).toMatchObject({ visits: 1, seconds: 2 });
    expect(visits.has('web_research')).toBe(false);
  });

  it('remembers the order in which nodes were first reached', () => {
    const order = [...visitsByNode(PIPELINE).entries()]
      .sort((a, b) => a[1].firstStep - b[1].firstStep)
      .map(([id]) => id);
    expect(order).toEqual([
      'preprocessing',
      'router',
      'review',
      'research_action',
      'reasoning',
      'answer_production',
    ]);
  });

  it('only looks at the steps up to the requested point of a replay', () => {
    const visits = visitsByNode(PIPELINE, 3);
    expect([...visits.keys()]).toEqual(['preprocessing', 'router', 'review']);
    expect(visits.get('review')?.visits).toBe(1);
  });

  it('marks a node as failed when any of its visits failed', () => {
    const visits = visitsByNode([step('a'), step('b', 1, 'boom')]);
    expect(visits.get('b')?.failed).toBe(true);
    expect(visits.get('a')?.failed).toBe(false);
  });

  it('is empty for no steps', () => {
    expect(visitsByNode([]).size).toBe(0);
  });
});

describe('traversedEdges', () => {
  it('links each step to the next one', () => {
    const edges = traversedEdges(PIPELINE, PIPELINE.length, true);
    expect(edges.has('preprocessing->router')).toBe(true);
    expect(edges.has('review->research_action')).toBe(true);
    expect(edges.has('research_action->review')).toBe(true);
    expect(edges.has('review->reasoning')).toBe(true);
    expect(edges.has('router->reasoning')).toBe(false);
  });

  it('reaches the end only when the run completed', () => {
    expect(traversedEdges(PIPELINE, PIPELINE.length, true).has(`answer_production->${END}`)).toBe(
      true,
    );
    expect(traversedEdges(PIPELINE, PIPELINE.length, false).has(`answer_production->${END}`)).toBe(
      false,
    );
  });

  it('does not reach the end part-way through a replay, nor after a failed last step', () => {
    expect(traversedEdges(PIPELINE, 3, true).has(`answer_production->${END}`)).toBe(false);
    const failing = [step('a'), step('b', 1, 'boom')];
    expect(traversedEdges(failing, 2, true).has(`b->${END}`)).toBe(false);
    expect(traversedEdges(failing, 2, true).has('a->b')).toBe(true);
  });

  it('is empty for a run with fewer than two steps and no end', () => {
    expect(traversedEdges([step('a')], 1, false).size).toBe(0);
    expect(traversedEdges([], 0, true).size).toBe(0);
  });
});

describe('failedStep', () => {
  it('finds where the run stopped', () => {
    expect(failedStep([step('a'), step('b', 1, 'boom')])?.node).toBe('b');
    expect(failedStep(PIPELINE)).toBeNull();
  });
});
