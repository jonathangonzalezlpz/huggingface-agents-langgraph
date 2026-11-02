import { describe, expect, it } from 'vitest';

import { diffDefinitions } from './diff';
import type { AgentDefinition, ArchitectureSummary } from './types';
import { groupVersions } from './versions';

const base: AgentDefinition = {
  schemaVersion: '4.0',
  architectureId: 'demo',
  stateType: 'AgentState',
  initialNode: 'a',
  nodes: [
    { id: 'a', implementationId: 'preprocessing', description: '' },
    { id: 'b', implementationId: 'reasoning', description: '' },
  ],
  edges: [
    { type: 'direct', source: 'a', target: 'b' },
    { type: 'direct', source: 'b', target: '__end__' },
  ],
};

const clone = (): AgentDefinition => structuredClone(base);

describe('diffDefinitions', () => {
  it('reports no difference between identical definitions', () => {
    const diff = diffDefinitions(base, clone());
    expect(diff.isEmpty).toBe(true);
    expect(diff).toMatchObject({
      nodesAdded: [],
      nodesRemoved: [],
      nodesChanged: [],
      edgesAdded: [],
      edgesRemoved: [],
      entryChanged: false,
    });
  });

  it('lists added nodes and the edges that come with them', () => {
    const next = clone();
    next.nodes.push({ id: 'c', implementationId: 'router', description: '' });
    next.edges.push({ type: 'direct', source: 'c', target: 'a' });
    const diff = diffDefinitions(base, next);
    expect(diff.nodesAdded).toEqual(['c']);
    expect(diff.edgesAdded).toEqual(['c → a']);
    expect(diff.isEmpty).toBe(false);
  });

  it('lists removed nodes and edges', () => {
    const next = clone();
    next.nodes = next.nodes.filter((n) => n.id !== 'b');
    next.edges = [];
    const diff = diffDefinitions(base, next);
    expect(diff.nodesRemoved).toEqual(['b']);
    expect(diff.edgesRemoved).toEqual(['a → b', 'b → end']);
  });

  it('sees a retargeted connection as one removal and one addition', () => {
    const next = clone();
    next.edges[0] = { type: 'direct', source: 'a', target: '__end__' };
    const diff = diffDefinitions(base, next);
    expect(diff.edgesRemoved).toEqual(['a → b']);
    expect(diff.edgesAdded).toEqual(['a → end']);
  });

  it('describes decision branches individually and detects a strategy change', () => {
    const decided = clone();
    decided.edges[0] = {
      type: 'conditional',
      source: 'a',
      routingStrategy: 'route_after_review',
      branches: { act: 'b', solve: '__end__' },
    };
    const changed = structuredClone(decided);
    if (changed.edges[0]?.type === 'conditional') {
      changed.edges[0].routingStrategy = 'route_after_router';
      changed.edges[0].branches = { act: 'b', solve: 'b' };
    }
    const diff = diffDefinitions(decided, changed);
    expect(diff.edgesRemoved).toContain('a ⟡ route_after_review');
    expect(diff.edgesAdded).toContain('a ⟡ route_after_router');
    expect(diff.edgesRemoved).toContain('a [solve] → end');
    expect(diff.edgesAdded).toContain('a [solve] → b');
  });

  it('reports a component swap, a new description and a new entry', () => {
    const next = clone();
    next.nodes[0] = { id: 'a', implementationId: 'router', description: '' };
    next.nodes[1] = { id: 'b', implementationId: 'reasoning', description: 'thinks' };
    next.initialNode = 'b';
    const diff = diffDefinitions(base, next);
    expect(diff.nodesChanged).toEqual(['a', 'b']);
    expect(diff.entryChanged).toBe(true);
  });

  it('ignores a rename of the architecture itself', () => {
    expect(diffDefinitions(base, { ...clone(), architectureId: 'other' }).isEmpty).toBe(true);
  });
});

const summary = (
  id: string,
  architectureId: string,
  version: number | null,
  readOnly = false,
): ArchitectureSummary => ({
  id,
  architectureId,
  version,
  parentId: null,
  contentSha256: id.padEnd(64, '0'),
  createdAt: version === null ? null : `2026-11-0${version}T00:00:00Z`,
  readOnly,
});

describe('groupVersions', () => {
  it('groups versions by architecture, newest first, with the built-in group first', () => {
    const groups = groupVersions([
      summary('s1', 'zeta', 1),
      summary('a2', 'alpha', 2),
      summary('a1', 'alpha', 1),
      summary('b', 'gaia_v31', null, true),
    ]);
    expect(groups.map((g) => g.architectureId)).toEqual(['gaia_v31', 'alpha', 'zeta']);
    expect(groups[1]?.versions.map((v) => v.version)).toEqual([2, 1]);
    expect(groups[1]?.latest.id).toBe('a2');
  });

  it('pairs every version with the one it came from for change summaries', () => {
    const [group] = groupVersions([
      summary('a1', 'alpha', 1),
      summary('a2', 'alpha', 2),
      summary('a3', 'alpha', 3),
    ]);
    expect(group?.versions.map((v) => v.previous?.id ?? null)).toEqual(['a2', 'a1', null]);
  });

  it('returns nothing for an empty library', () => {
    expect(groupVersions([])).toEqual([]);
  });
});
