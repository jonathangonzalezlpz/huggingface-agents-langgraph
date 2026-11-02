import { describe, expect, it } from 'vitest';

import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { fromDefinition } from '../../domain/editor/convert';
import { END } from '../../domain/editor/model';
import type { RunStep } from '../../domain/run';
import { computeLayout } from '../editor/autoLayout';
import { START_ID, projectGraph, type ComponentFlowNode } from '../editor/projection';
import { applyRunOverlay } from './overlay';

const services = createMemoryServices();
const catalog = await services.catalog.getCatalog();
const [summary] = await services.architectures.list();
const builtin = await services.architectures.get(summary?.id ?? '');
const { graph } = fromDefinition(builtin.definition, catalog);
const projected = projectGraph({ graph, layout: computeLayout(graph) }, catalog);

const step = (node: string, error: string | null = null): RunStep => ({
  node,
  durationSeconds: 2,
  error,
  updatedFields: [],
});

const PATH = [
  'preprocessing',
  'router',
  'web_research',
  'review',
  'reasoning',
  'answer_production',
];
const steps = PATH.map((node) => step(node));

const stateOf = (nodes: ReturnType<typeof applyRunOverlay>['nodes'], id: string) =>
  (nodes.find((n) => n.id === id) as ComponentFlowNode | undefined)?.data.run?.state;

describe('applyRunOverlay', () => {
  it('marks visited nodes, the one running now, and dims the rest', () => {
    const { nodes } = applyRunOverlay(projected, { steps, position: 4, completed: true });
    expect(stateOf(nodes, 'preprocessing')).toBe('visited');
    expect(stateOf(nodes, 'review')).toBe('active');
    expect(stateOf(nodes, 'reasoning')).toBe('skipped');
    expect(stateOf(nodes, 'code_processing')).toBe('skipped');
  });

  it('counts repeated visits and adds up their time', () => {
    const loop = [step('review'), step('research_action'), step('review')];
    const { nodes } = applyRunOverlay(projected, { steps: loop, position: 3, completed: false });
    const review = nodes.find((n) => n.id === 'review') as ComponentFlowNode;
    expect(review.data.run).toMatchObject({ visits: 2, seconds: 4 });
  });

  it('shows the node where the run failed', () => {
    const failing = [step('preprocessing'), step('router', 'boom')];
    const { nodes } = applyRunOverlay(projected, { steps: failing, position: 2, completed: false });
    expect(stateOf(nodes, 'router')).toBe('failed');
  });

  it('shows no node as failed before the replay reaches the failing step', () => {
    const failing = [step('preprocessing'), step('router', 'boom')];
    const { nodes } = applyRunOverlay(projected, { steps: failing, position: 1, completed: false });
    expect(stateOf(nodes, 'router')).toBe('skipped');
  });

  it('highlights the connections the run went through and mutes the others', () => {
    const { edges } = applyRunOverlay(projected, {
      steps,
      position: steps.length,
      completed: true,
    });
    const taken = edges.find((e) => e.source === 'router' && e.target === 'web_research');
    const other = edges.find((e) => e.source === 'router' && e.target === 'code_processing');
    expect(taken?.style?.stroke).toBe('var(--accent)');
    expect(Number(other?.style?.opacity)).toBeLessThan(0.5);
    const toEnd = edges.find((e) => e.source === 'answer_production' && e.target === END);
    expect(toEnd?.style?.stroke).toBe('var(--accent)');
  });

  it('keeps the start marker highlighted as soon as the run has begun', () => {
    const begun = applyRunOverlay(projected, { steps, position: 1, completed: true });
    expect(begun.edges.find((e) => e.source === START_ID)?.style?.stroke).toBe('var(--accent)');
    const not = applyRunOverlay(projected, { steps, position: 0, completed: true });
    expect(Number(not.edges.find((e) => e.source === START_ID)?.style?.opacity)).toBeLessThan(0.5);
  });

  it('does not change the projection it was given', () => {
    const before = JSON.stringify(projected.edges.map((e) => e.style));
    applyRunOverlay(projected, { steps, position: steps.length, completed: true });
    expect(JSON.stringify(projected.edges.map((e) => e.style))).toBe(before);
  });
});
