import { describe, expect, it } from 'vitest';

import demo from '../../adapters/memory/demo-data.json';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import type { Catalog } from '../types';
import {
  addNode,
  applyLayout,
  clearDecision,
  connect,
  connectBranch,
  disconnect,
  disconnectBranch,
  moveNodes,
  removeNode,
  renameArchitecture,
  renameNode,
  setDecision,
  setDescription,
  setInitial,
  type CommandResult,
} from './commands';
import { fromDefinition, toDefinition, unexportableDecisions } from './convert';
import { commit, createHistory, redo, undo } from './history';
import { END, checkInvariants, findNode, type EditorDocument } from './model';
import { blankDocument, documentFromArchitecture, linearDocument } from './templates';

const services = createMemoryServices();
const catalog: Catalog = await services.catalog.getCatalog();
const [summary] = await services.architectures.list();
const builtin = await services.architectures.get(summary?.id ?? '');

function ok(result: CommandResult): EditorDocument {
  if (!result.ok) throw new Error(`rejected: ${result.reason.code}`);
  return result.doc;
}

const POSITION = { x: 10, y: 20 };

function twoNodes(): EditorDocument {
  let doc = blankDocument('demo');
  doc = ok(addNode(doc, catalog, 'preprocessing', POSITION));
  doc = ok(addNode(doc, catalog, 'reasoning', { x: 300, y: 20 }));
  return doc;
}

describe('conversion', () => {
  it('round-trips the built-in V3.1 pipeline without any change', () => {
    const { graph, issues } = fromDefinition(builtin.definition, catalog);
    expect(issues).toEqual([]);
    expect(toDefinition(graph)).toEqual(builtin.definition);
  });

  it('turns the three routing edges into decisions with every branch listed', () => {
    const { graph } = fromDefinition(builtin.definition, catalog);
    const router = findNode(graph, 'router');
    expect(router?.outgoing.kind).toBe('decision');
    if (router?.outgoing.kind === 'decision') {
      expect(Object.keys(router.outgoing.branches).sort()).toEqual([
        'code',
        'direct',
        'document',
        'finish',
        'multimedia',
        'spreadsheet',
        'web',
      ]);
      expect(router.outgoing.branches['direct']).toBe('review');
    }
  });

  it('shows branches the stored definition lacks as unconnected', () => {
    const definition = structuredClone(builtin.definition);
    const router = definition.edges.find((e) => e.type === 'conditional' && e.source === 'router');
    if (router?.type === 'conditional') delete router.branches['web'];
    const { graph } = fromDefinition(definition, catalog);
    const node = findNode(graph, 'router');
    expect(node?.outgoing.kind === 'decision' && node.outgoing.branches['web']).toBeNull();
  });

  it('reports what the editor cannot represent instead of hiding it', () => {
    const definition = structuredClone(builtin.definition);
    definition.edges.push({ type: 'direct', source: 'router', target: 'review' });
    definition.edges.push({ type: 'direct', source: 'ghost', target: 'review' });
    definition.initialNode = 'ghost';
    const { issues } = fromDefinition(definition, catalog);
    expect(issues.map((i) => i.code).sort()).toEqual([
      'multiple-outgoing',
      'unknown-initial',
      'unknown-source',
    ]);
  });

  it('ignores edges from the start marker and normalizes end aliases', () => {
    const definition = structuredClone(builtin.definition);
    definition.edges.push({ type: 'direct', source: '__start__', target: 'preprocessing' });
    const answer = definition.edges.find(
      (e) => e.type === 'direct' && e.source === 'answer_production',
    );
    if (answer?.type === 'direct') answer.target = 'END';
    const { graph, issues } = fromDefinition(definition, catalog);
    expect(issues).toEqual([]);
    expect(findNode(graph, 'answer_production')?.outgoing).toEqual({ kind: 'direct', target: END });
  });

  it('exports pending branches as absent and drops decisions with no connected branch', () => {
    let doc = twoNodes();
    doc = ok(setDecision(doc, catalog, 'preprocessing', 'route_after_review'));
    expect(toDefinition(doc.graph).edges).toEqual([]);
    doc = ok(connectBranch(doc, 'preprocessing', 'act', 'reasoning'));
    const [edge] = toDefinition(doc.graph).edges;
    expect(edge).toEqual({
      type: 'conditional',
      source: 'preprocessing',
      routingStrategy: 'route_after_review',
      branches: { act: 'reasoning' },
    });
  });
});

describe('nodes', () => {
  it('adds components with unique ids and the first one becomes the entry', () => {
    let doc = blankDocument('demo');
    doc = ok(addNode(doc, catalog, 'reasoning', POSITION));
    doc = ok(addNode(doc, catalog, 'reasoning', { x: 1, y: 1 }));
    expect(doc.graph.nodes.map((n) => n.id)).toEqual(['reasoning', 'reasoning_2']);
    expect(doc.graph.initialNode).toBe('reasoning');
    expect(doc.layout['reasoning_2']).toEqual({ x: 1, y: 1 });
  });

  it('rejects unknown components and invalid or duplicate ids', () => {
    const doc = twoNodes();
    const code = (r: CommandResult) => (r.ok ? 'ok' : r.reason.code);
    expect(code(addNode(doc, catalog, 'nope', POSITION))).toBe('unknown-component');
    expect(code(addNode(doc, catalog, 'reasoning', POSITION, 'preprocessing'))).toBe(
      'duplicate-id',
    );
    for (const bad of ['', '   ', '__start__', '__end__', 'START', 'END', 'x'.repeat(101)]) {
      expect(code(addNode(doc, catalog, 'reasoning', POSITION, bad)), bad).toBe('invalid-id');
    }
  });

  it('renames a node and every reference to it', () => {
    let doc = twoNodes();
    doc = ok(connect(doc, 'preprocessing', 'reasoning'));
    doc = ok(renameNode(doc, 'reasoning', 'think'));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({
      kind: 'direct',
      target: 'think',
    });
    expect(doc.layout['think']).toEqual({ x: 300, y: 20 });
    expect('reasoning' in doc.layout).toBe(false);
    doc = ok(renameNode(doc, 'preprocessing', 'start_here'));
    expect(doc.graph.initialNode).toBe('start_here');
    expect(checkInvariants(doc)).toEqual([]);
  });

  it('removes a node and leaves its former sources unconnected', () => {
    let doc = twoNodes();
    doc = ok(connect(doc, 'preprocessing', 'reasoning'));
    doc = ok(removeNode(doc, 'reasoning'));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({ kind: 'none' });
    expect(doc.layout['reasoning']).toBeUndefined();
  });

  it('moves the entry to another node when the entry is removed, or to none', () => {
    let doc = twoNodes();
    doc = ok(removeNode(doc, 'preprocessing'));
    expect(doc.graph.initialNode).toBe('reasoning');
    doc = ok(removeNode(doc, 'reasoning'));
    expect(doc.graph.initialNode).toBeNull();
  });

  it('sets the entry only to an existing node', () => {
    const doc = twoNodes();
    expect(ok(setInitial(doc, 'reasoning')).graph.initialNode).toBe('reasoning');
    expect(setInitial(doc, 'ghost')).toMatchObject({ ok: false });
  });
});

describe('connections', () => {
  it('connects, retargets and disconnects a direct output', () => {
    let doc = twoNodes();
    doc = ok(connect(doc, 'preprocessing', 'reasoning'));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({
      kind: 'direct',
      target: 'reasoning',
    });
    doc = ok(connect(doc, 'preprocessing', END));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({ kind: 'direct', target: END });
    doc = ok(disconnect(doc, 'preprocessing'));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({ kind: 'none' });
  });

  it('cannot represent a second output, a start target or unknown nodes', () => {
    const doc = ok(setDecision(twoNodes(), catalog, 'preprocessing', 'route_after_review'));
    expect(connect(doc, 'preprocessing', 'reasoning')).toMatchObject({
      ok: false,
      reason: { code: 'has-decision' },
    });
    expect(connect(twoNodes(), 'preprocessing', '__start__')).toMatchObject({
      ok: false,
      reason: { code: 'unknown-node' },
    });
    expect(connect(twoNodes(), 'ghost', 'reasoning')).toMatchObject({ ok: false });
    expect(connect(twoNodes(), 'preprocessing', 'ghost')).toMatchObject({ ok: false });
  });

  it('allows a node to loop back to itself, as the backend does', () => {
    const doc = ok(connect(twoNodes(), 'reasoning', 'reasoning'));
    expect(checkInvariants(doc)).toEqual([]);
  });

  it('manages decisions and their branches', () => {
    let doc = twoNodes();
    doc = ok(connect(doc, 'preprocessing', 'reasoning'));
    doc = ok(setDecision(doc, catalog, 'preprocessing', 'route_after_review'));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({
      kind: 'decision',
      strategy: 'route_after_review',
      branches: { act: null, solve: null },
    });
    doc = ok(connectBranch(doc, 'preprocessing', 'solve', 'reasoning'));
    doc = ok(connectBranch(doc, 'preprocessing', 'act', END));
    doc = ok(disconnectBranch(doc, 'preprocessing', 'act'));
    const outgoing = findNode(doc.graph, 'preprocessing')?.outgoing;
    expect(outgoing).toMatchObject({ branches: { act: null, solve: 'reasoning' } });
    doc = ok(clearDecision(doc, 'preprocessing'));
    expect(findNode(doc.graph, 'preprocessing')?.outgoing).toEqual({ kind: 'none' });
  });

  it('rejects branches the strategy does not define and unknown strategies', () => {
    const doc = ok(setDecision(twoNodes(), catalog, 'preprocessing', 'route_after_review'));
    expect(connectBranch(doc, 'preprocessing', 'nope', 'reasoning')).toMatchObject({
      reason: { code: 'unknown-branch' },
    });
    expect(setDecision(twoNodes(), catalog, 'preprocessing', 'nope')).toMatchObject({
      reason: { code: 'unknown-strategy' },
    });
    expect(connectBranch(twoNodes(), 'preprocessing', 'act', 'reasoning')).toMatchObject({
      reason: { code: 'no-decision' },
    });
  });

  it('returns the very same document for commands that change nothing', () => {
    const unconnected = twoNodes();
    expect(ok(disconnect(unconnected, 'preprocessing'))).toBe(unconnected);
    expect(ok(clearDecision(unconnected, 'preprocessing'))).toBe(unconnected);

    const doc = ok(connect(unconnected, 'preprocessing', 'reasoning'));
    expect(ok(connect(doc, 'preprocessing', 'reasoning'))).toBe(doc);
    expect(ok(moveNodes(doc, { preprocessing: POSITION }))).toBe(doc);
    expect(ok(setInitial(doc, 'preprocessing'))).toBe(doc);
  });
});

describe('layout', () => {
  it('moves nodes and applies computed layouts in a single step', () => {
    const doc = twoNodes();
    const moved = ok(moveNodes(doc, { reasoning: { x: 5, y: 6 } }));
    expect(moved.layout['reasoning']).toEqual({ x: 5, y: 6 });
    expect(moved.graph).toBe(doc.graph);
    const laidOut = ok(
      applyLayout(doc, { preprocessing: { x: 0, y: 0 }, reasoning: { x: 100, y: 0 } }),
    );
    expect(laidOut.layout).toEqual({ preprocessing: { x: 0, y: 0 }, reasoning: { x: 100, y: 0 } });
  });

  it('rejects positions for unknown nodes or non-finite coordinates', () => {
    const doc = twoNodes();
    expect(moveNodes(doc, { ghost: POSITION })).toMatchObject({ ok: false });
    expect(moveNodes(doc, { reasoning: { x: Number.NaN, y: 0 } })).toMatchObject({ ok: false });
  });
});

describe('history', () => {
  it('undoes and redoes whole steps and discards the redo branch on new edits', () => {
    let history = createHistory(blankDocument('demo'));
    history = commit(history, ok(addNode(history.present, catalog, 'reasoning', POSITION)));
    history = commit(history, ok(addNode(history.present, catalog, 'router', POSITION)));
    expect(history.present.graph.nodes).toHaveLength(2);
    history = undo(history);
    expect(history.present.graph.nodes).toHaveLength(1);
    history = redo(history);
    expect(history.present.graph.nodes).toHaveLength(2);
    history = undo(undo(history));
    history = commit(history, ok(addNode(history.present, catalog, 'review', POSITION)));
    expect(history.future).toHaveLength(0);
    expect(history.present.graph.nodes.map((n) => n.id)).toEqual(['review']);
  });

  it('ignores no-op commits and empty undo or redo', () => {
    const initial = createHistory(twoNodes());
    expect(commit(initial, initial.present)).toBe(initial);
    expect(undo(initial)).toBe(initial);
    expect(redo(initial)).toBe(initial);
  });

  it('keeps a bounded number of steps', () => {
    let history = createHistory(blankDocument('demo'), 3);
    for (let i = 0; i < 10; i += 1) {
      history = commit(history, ok(addNode(history.present, catalog, 'reasoning', POSITION)));
    }
    expect(history.past).toHaveLength(3);
  });
});

describe('templates', () => {
  it('starts from an empty graph', () => {
    const doc = blankDocument('mine');
    expect(doc.graph).toMatchObject({ architectureId: 'mine', nodes: [], initialNode: null });
  });

  it('builds a valid minimal pipeline from catalog components', () => {
    const doc = linearDocument('mine', catalog);
    expect(doc.graph.nodes.map((n) => n.implementationId)).toEqual([
      'preprocessing',
      'reasoning',
      'answer_production',
    ]);
    expect(doc.graph.initialNode).toBe('preprocessing');
    expect(findNode(doc.graph, 'answer_production')?.outgoing).toEqual({
      kind: 'direct',
      target: END,
    });
    expect(checkInvariants(doc)).toEqual([]);
  });

  it('refuses to build the minimal pipeline when the catalog lacks its components', () => {
    expect(() => linearDocument('mine', { ...catalog, components: [] })).toThrow(/preprocessing/);
  });

  it('duplicates an architecture under a new name, keeping its stored layout', () => {
    const doc = documentFromArchitecture(builtin, catalog, 'copy', { router: { x: 9, y: 9 } });
    expect(doc.graph.architectureId).toBe('copy');
    expect(doc.graph.nodes).toHaveLength(12);
    expect(doc.layout['router']).toEqual({ x: 9, y: 9 });
    expect(toDefinition(doc.graph)).toEqual({ ...builtin.definition, architectureId: 'copy' });
  });
});

describe('invariants under arbitrary command sequences', () => {
  it('never produce a document that breaks the model rules', () => {
    // Deterministic pseudo-random generator so a failure is reproducible.
    let seed = 20261101;
    const random = (n: number) => {
      seed = (seed * 1664525 + 1013904223) % 2 ** 32;
      return seed % n;
    };
    const components = catalog.components.map((c) => c.implementationId);
    const strategies = catalog.routingStrategies;
    let doc = blankDocument('fuzz');
    for (let step = 0; step < 1500; step += 1) {
      const ids = [...doc.graph.nodes.map((n) => n.id), 'ghost', END, '__start__'];
      const pick = () => ids[random(ids.length)] ?? 'ghost';
      const strategy = strategies[random(strategies.length)];
      const label = strategy?.outputs[random(strategy.outputs.length)] ?? 'x';
      const attempts: CommandResult[] = [
        addNode(doc, catalog, components[random(components.length)] ?? 'nope', { x: step, y: 0 }),
        removeNode(doc, pick()),
        renameNode(doc, pick(), `n${random(40)}`),
        setInitial(doc, pick()),
        connect(doc, pick(), pick()),
        disconnect(doc, pick()),
        setDecision(doc, catalog, pick(), strategy?.identifier ?? 'nope'),
        clearDecision(doc, pick()),
        connectBranch(doc, pick(), label, pick()),
        disconnectBranch(doc, pick(), label),
        moveNodes(doc, { [pick()]: { x: random(500), y: random(500) } }),
      ];
      const chosen = attempts[random(attempts.length)];
      if (chosen?.ok) doc = chosen.doc;
      expect(checkInvariants(doc), `step ${step}`).toEqual([]);
    }
    expect(doc.graph.nodes.length).toBeGreaterThan(0);
  });
});

it('uses the demo fixture the backend generated', () => {
  expect(demo.architecture.id).toBe('builtin:gaia_v31');
});

describe('descriptions and the architecture name', () => {
  it('sets a node description and ignores an unchanged one', () => {
    const doc = twoNodes();
    const described = ok(setDescription(doc, 'reasoning', 'Thinks about it'));
    expect(findNode(described.graph, 'reasoning')?.description).toBe('Thinks about it');
    expect(ok(setDescription(described, 'reasoning', 'Thinks about it'))).toBe(described);
    expect(setDescription(doc, 'ghost', 'x')).toMatchObject({ reason: { code: 'unknown-node' } });
  });

  it('refuses descriptions that are too long', () => {
    expect(setDescription(twoNodes(), 'reasoning', 'x'.repeat(501))).toMatchObject({
      reason: { code: 'invalid-description' },
    });
  });

  it('renames the architecture within the model rules', () => {
    const doc = twoNodes();
    expect(ok(renameArchitecture(doc, 'mi_agente')).graph.architectureId).toBe('mi_agente');
    expect(ok(renameArchitecture(doc, 'demo'))).toBe(doc);
    for (const bad of ['', '  ', ' padded ', 'x'.repeat(101)]) {
      expect(renameArchitecture(doc, bad), bad).toMatchObject({ reason: { code: 'invalid-name' } });
    }
    expect(renameArchitecture(doc, 'gaia_v31')).toMatchObject({
      reason: { code: 'reserved-name' },
    });
  });

  it('keeps node ids, connections and layout untouched when renaming the architecture', () => {
    const doc = ok(connect(twoNodes(), 'preprocessing', 'reasoning'));
    const renamed = ok(renameArchitecture(doc, 'otro'));
    expect(renamed.graph.nodes).toBe(doc.graph.nodes);
    expect(renamed.layout).toBe(doc.layout);
  });
});

describe('decisions that cannot be stored', () => {
  it('lists decisions with no connected branch, which the export leaves out', () => {
    let doc = twoNodes();
    doc = ok(setDecision(doc, catalog, 'preprocessing', 'route_after_review'));
    expect(unexportableDecisions(doc.graph)).toEqual(['preprocessing']);
    doc = ok(connectBranch(doc, 'preprocessing', 'act', 'reasoning'));
    expect(unexportableDecisions(doc.graph)).toEqual([]);
  });

  it('ignores nodes without a decision', () => {
    expect(unexportableDecisions(twoNodes().graph)).toEqual([]);
    expect(unexportableDecisions(linearDocument('x', catalog).graph)).toEqual([]);
  });
});
