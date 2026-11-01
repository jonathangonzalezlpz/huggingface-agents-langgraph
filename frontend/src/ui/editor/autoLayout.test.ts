import { describe, expect, it } from 'vitest';

import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { fromDefinition } from '../../domain/editor/convert';
import { END } from '../../domain/editor/model';
import { blankDocument, linearDocument } from '../../domain/editor/templates';
import { computeLayout, nodeHeight, NODE_WIDTH } from './autoLayout';

const services = createMemoryServices();
const catalog = await services.catalog.getCatalog();
const [summary] = await services.architectures.list();
const builtin = await services.architectures.get(summary?.id ?? '');
const { graph: v31 } = fromDefinition(builtin.definition, catalog);

describe('computeLayout', () => {
  it('places every node exactly once with finite coordinates and never places terminals', () => {
    const positions = computeLayout(v31);
    expect(Object.keys(positions).sort()).toEqual(v31.nodes.map((n) => n.id).sort());
    for (const point of Object.values(positions)) {
      expect(Number.isFinite(point.x) && Number.isFinite(point.y)).toBe(true);
    }
    expect(positions[END]).toBeUndefined();
  });

  it('flows left to right along the pipeline', () => {
    const p = computeLayout(v31);
    const x = (id: string) => p[id]?.x ?? Number.NaN;
    expect(x('preprocessing')).toBeLessThan(x('router'));
    expect(x('router')).toBeLessThan(x('code_processing'));
    expect(x('code_processing')).toBeLessThan(x('review'));
    expect(x('review')).toBeLessThan(x('reasoning'));
    expect(x('reasoning')).toBeLessThan(x('answer_production'));
  });

  it('keeps nodes of the same layer apart so they do not overlap', () => {
    const p = computeLayout(v31);
    const nodes = v31.nodes;
    for (const a of nodes) {
      for (const b of nodes) {
        if (a.id >= b.id) continue;
        const pa = p[a.id];
        const pb = p[b.id];
        if (!pa || !pb) continue;
        const overlapX = Math.abs(pa.x - pb.x) < NODE_WIDTH;
        const overlapY = Math.abs(pa.y - pb.y) < Math.min(nodeHeight(a), nodeHeight(b));
        expect(overlapX && overlapY, `${a.id} overlaps ${b.id}`).toBe(false);
      }
    }
  });

  it('handles the review and research cycle without failing', () => {
    expect(() => computeLayout(v31)).not.toThrow();
    const p = computeLayout(v31);
    expect(p['review']).toBeDefined();
    expect(p['research_action']).toBeDefined();
  });

  it('is deterministic', () => {
    expect(computeLayout(v31)).toEqual(computeLayout(v31));
  });

  it('lays out small and empty graphs', () => {
    expect(computeLayout(blankDocument('x').graph)).toEqual({});
    const linear = computeLayout(linearDocument('x', catalog).graph);
    expect(Object.keys(linear)).toHaveLength(3);
  });

  it('gives decision nodes more height for their branch rows', () => {
    const router = v31.nodes.find((n) => n.id === 'router');
    const reasoning = v31.nodes.find((n) => n.id === 'reasoning');
    expect(router && reasoning && nodeHeight(router) > nodeHeight(reasoning)).toBe(true);
  });
});
