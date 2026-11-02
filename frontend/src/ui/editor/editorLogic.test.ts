import { describe, expect, it } from 'vitest';

import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { addNode, connect, removeNode, setDecision } from '../../domain/editor/commands';
import { fromDefinition } from '../../domain/editor/convert';
import { END } from '../../domain/editor/model';
import { blankDocument, linearDocument } from '../../domain/editor/templates';
import type { Diagnostic } from '../../domain/types';
import { computeLayout } from './autoLayout';
import { editorReducer, initialState, sequence } from './editorState';
import {
  END_ID,
  START_ID,
  branchHandle,
  branchOfHandle,
  projectGraph,
  type ComponentFlowNode,
} from './projection';

const services = createMemoryServices();
const catalog = await services.catalog.getCatalog();
const [summary] = await services.architectures.list();
const builtin = await services.architectures.get(summary?.id ?? '');
const { graph: v31 } = fromDefinition(builtin.definition, catalog);
const v31Doc = { graph: v31, layout: computeLayout(v31) };

describe('projectGraph', () => {
  const { nodes, edges } = projectGraph(v31Doc, catalog);

  it('draws every component plus the start and end markers', () => {
    expect(nodes).toHaveLength(14);
    expect(
      nodes
        .filter((n) => n.type === 'terminal')
        .map((n) => n.id)
        .sort(),
    ).toEqual([END_ID, START_ID]);
  });

  it('draws one edge per direct output, per connected branch and for the entry', () => {
    const direct = v31.nodes.filter((n) => n.outgoing.kind === 'direct').length;
    const branches = 2 + 7 + 2;
    expect(edges).toHaveLength(direct + branches + 1);
    expect(edges.filter((e) => e.source === START_ID)).toHaveLength(1);
  });

  it('sends the pipeline end to the end marker and labels each branch', () => {
    const last = edges.find((e) => e.source === 'answer_production');
    expect(last?.target).toBe(END_ID);
    const web = edges.find((e) => e.source === 'router' && e.label === 'web');
    expect(web).toMatchObject({ sourceHandle: branchHandle('web'), target: 'web_research' });
  });

  it('leaves unconnected branches without an edge', () => {
    let doc = linearDocument('x', catalog);
    doc = (() => {
      const r = removeNode(doc, 'reasoning');
      return r.ok ? r.doc : doc;
    })();
    const decided = setDecision(doc, catalog, 'preprocessing', 'route_after_review');
    if (!decided.ok) throw new Error('setup');
    const projected = projectGraph(decided.doc, catalog);
    expect(projected.edges.filter((e) => e.source === 'preprocessing')).toHaveLength(0);
  });

  it('uses the stored layout, lets a live drag override it, and computes missing positions', () => {
    const base = projectGraph(v31Doc, catalog).nodes.find((n) => n.id === 'router');
    const dragged = projectGraph(v31Doc, catalog, [], { router: { x: 7, y: 9 } }).nodes.find(
      (n) => n.id === 'router',
    );
    expect(dragged?.position).toEqual({ x: 7, y: 9 });
    expect(base?.position).toEqual(v31Doc.layout['router']);
    const bare = projectGraph({ graph: v31, layout: {} }, catalog).nodes.find(
      (n) => n.id === 'router',
    );
    expect(bare?.position).toEqual(computeLayout(v31)['router']);
  });

  it('marks the entry and attaches the worst diagnostic to each node', () => {
    const diagnostics: Diagnostic[] = [
      { code: 'A', severity: 'warning', message: 'w', nodeId: 'review' },
      { code: 'B', severity: 'error', message: 'e', nodeId: 'review' },
      { code: 'C', severity: 'info', message: 'i', edgeSource: 'router' },
    ];
    const projected = projectGraph(v31Doc, catalog, diagnostics).nodes.filter(
      (n): n is ComponentFlowNode => n.type === 'component',
    );
    const byId = Object.fromEntries(projected.map((n) => [n.id, n.data]));
    expect(byId['preprocessing']?.isEntry).toBe(true);
    expect(byId['router']?.isEntry).toBe(false);
    expect(byId['review']).toMatchObject({ severity: 'error', diagnosticCount: 2 });
    expect(byId['router']).toMatchObject({ severity: 'info', diagnosticCount: 1 });
    expect(byId['reasoning']).toMatchObject({ severity: null, diagnosticCount: 0 });
  });

  it('shows nothing but the markers rules for an empty graph', () => {
    expect(projectGraph(blankDocument('x'), catalog)).toEqual({ nodes: [], edges: [] });
  });

  it('encodes and decodes branch handles', () => {
    expect(branchOfHandle(branchHandle('act'))).toBe('act');
    expect(branchOfHandle('out')).toBeNull();
    expect(branchOfHandle(null)).toBeNull();
  });
});

describe('editorReducer', () => {
  const start = () => initialState(blankDocument('demo'));
  const add = (id: string) => (doc: Parameters<typeof addNode>[0]) =>
    addNode(doc, catalog, 'reasoning', { x: 0, y: 0 }, id);

  it('applies a command, records history and announces it', () => {
    const state = editorReducer(start(), {
      type: 'apply',
      run: add('a'),
      announce: (doc) => ({
        key: 'editor.announce.added',
        params: { id: doc.graph.nodes[0]?.id ?? '' },
      }),
    });
    expect(state.history.present.graph.nodes).toHaveLength(1);
    expect(state.history.past).toHaveLength(1);
    expect(state.announcement).toMatchObject({ key: 'editor.announce.added', params: { id: 'a' } });
  });

  it('keeps the document and reports the reason when a command is rejected', () => {
    const state = editorReducer(start(), { type: 'apply', run: (d) => connect(d, 'x', 'y') });
    expect(state.history.past).toHaveLength(0);
    expect(state.notice).toMatchObject({ code: 'unknown-node' });
    expect(editorReducer(state, { type: 'dismissNotice' }).notice).toBeNull();
  });

  it('records nothing for commands that change nothing', () => {
    const afterAdd = editorReducer(start(), { type: 'apply', run: add('a') });
    const again = editorReducer(afterAdd, { type: 'apply', run: (d) => connect(d, 'a', END) });
    const repeated = editorReducer(again, { type: 'apply', run: (d) => connect(d, 'a', END) });
    expect(repeated.history).toBe(again.history);
  });

  it('undoes and redoes with announcements, and ignores undo with nothing to undo', () => {
    const added = editorReducer(start(), { type: 'apply', run: add('a') });
    const undone = editorReducer(added, { type: 'undo' });
    expect(undone.history.present.graph.nodes).toHaveLength(0);
    expect(undone.announcement?.key).toBe('editor.announce.undone');
    const redone = editorReducer(undone, { type: 'redo' });
    expect(redone.history.present.graph.nodes).toHaveLength(1);
    expect(redone.announcement?.key).toBe('editor.announce.redone');
    expect(editorReducer(start(), { type: 'undo' })).toEqual(start());
  });

  it('gives repeated identical announcements a new serial so they are read again', () => {
    let state = editorReducer(start(), { type: 'apply', run: add('a') });
    state = editorReducer(state, { type: 'undo' });
    const first = state.announcement?.serial;
    state = editorReducer(state, { type: 'redo' });
    state = editorReducer(state, { type: 'undo' });
    expect(state.announcement?.serial).toBeGreaterThan(first ?? 0);
  });
});

describe('sequence', () => {
  it('runs steps as one command and stops at the first rejection', () => {
    const run = sequence(
      (d) => addNode(d, catalog, 'reasoning', { x: 0, y: 0 }, 'a'),
      (d) => addNode(d, catalog, 'router', { x: 1, y: 1 }, 'b'),
      (d) => connect(d, 'a', 'b'),
    );
    const result = run(blankDocument('x'));
    expect(result.ok && result.doc.graph.nodes.map((n) => n.id)).toEqual(['a', 'b']);
    const failing = sequence((d) => connect(d, 'a', 'b'));
    expect(failing(blankDocument('x'))).toMatchObject({ ok: false });
  });
});
