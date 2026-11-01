import type { Catalog } from '../types';
import {
  END,
  findNode,
  idProblem,
  type EditorDocument,
  type EditorGraph,
  type EditorNode,
  type Outgoing,
  type Point,
  type Target,
} from './model';

export type RejectionCode =
  | 'invalid-id'
  | 'duplicate-id'
  | 'unknown-node'
  | 'unknown-component'
  | 'unknown-strategy'
  | 'unknown-branch'
  | 'has-decision'
  | 'no-decision'
  | 'invalid-position'
  | 'invalid-description'
  | 'invalid-name'
  | 'reserved-name';

export interface Rejection {
  code: RejectionCode;
  /** The id, label or component the rejection is about. */
  subject?: string;
}

export type CommandResult = { ok: true; doc: EditorDocument } | { ok: false; reason: Rejection };

const rejected = (code: RejectionCode, subject?: string): CommandResult => ({
  ok: false,
  reason: subject === undefined ? { code } : { code, subject },
});

/** A command that changes nothing returns the very same document, so history can skip it. */
const accepted = (doc: EditorDocument): CommandResult => ({ ok: true, doc });

function withNode(doc: EditorDocument, id: string, change: (node: EditorNode) => EditorNode) {
  const graph: EditorGraph = {
    ...doc.graph,
    nodes: doc.graph.nodes.map((node) => (node.id === id ? change(node) : node)),
  };
  return { ...doc, graph };
}

const isTarget = (graph: EditorGraph, target: Target) =>
  target === END || !!findNode(graph, target);

/** The id a new node of this component would get. */
export function uniqueNodeId(graph: EditorGraph, base: string): string {
  if (!findNode(graph, base)) return base;
  for (let n = 2; ; n += 1) {
    if (!findNode(graph, `${base}_${n}`)) return `${base}_${n}`;
  }
}

export function addNode(
  doc: EditorDocument,
  catalog: Catalog,
  implementationId: string,
  position: Point,
  id?: string,
): CommandResult {
  if (!catalog.components.some((c) => c.implementationId === implementationId)) {
    return rejected('unknown-component', implementationId);
  }
  if (!isFinitePoint(position)) return rejected('invalid-position');
  if (id !== undefined) {
    if (idProblem(id)) return rejected('invalid-id', id);
    if (findNode(doc.graph, id)) return rejected('duplicate-id', id);
  }
  const nodeId = id ?? uniqueNodeId(doc.graph, implementationId);
  const node: EditorNode = {
    id: nodeId,
    implementationId,
    description: '',
    outgoing: { kind: 'none' },
  };
  return accepted({
    graph: {
      ...doc.graph,
      initialNode: doc.graph.initialNode ?? nodeId,
      nodes: [...doc.graph.nodes, node],
    },
    layout: { ...doc.layout, [nodeId]: position },
  });
}

/** Drop every reference to a node, leaving the sources that pointed at it unconnected. */
function withoutReferences(outgoing: Outgoing, id: string): Outgoing {
  if (outgoing.kind === 'direct') return outgoing.target === id ? { kind: 'none' } : outgoing;
  if (outgoing.kind === 'decision') {
    const branches = Object.fromEntries(
      Object.entries(outgoing.branches).map(([label, target]) => [
        label,
        target === id ? null : target,
      ]),
    );
    return { ...outgoing, branches };
  }
  return outgoing;
}

export function removeNode(doc: EditorDocument, id: string): CommandResult {
  if (!findNode(doc.graph, id)) return rejected('unknown-node', id);
  const nodes = doc.graph.nodes
    .filter((node) => node.id !== id)
    .map((node) => ({ ...node, outgoing: withoutReferences(node.outgoing, id) }));
  const layout = Object.fromEntries(Object.entries(doc.layout).filter(([key]) => key !== id));
  const initialNode = doc.graph.initialNode === id ? (nodes[0]?.id ?? null) : doc.graph.initialNode;
  return accepted({ graph: { ...doc.graph, nodes, initialNode }, layout });
}

function retarget(outgoing: Outgoing, from: string, to: string): Outgoing {
  if (outgoing.kind === 'direct') {
    return outgoing.target === from ? { kind: 'direct', target: to } : outgoing;
  }
  if (outgoing.kind === 'decision') {
    const branches = Object.fromEntries(
      Object.entries(outgoing.branches).map(([label, target]) => [
        label,
        target === from ? to : target,
      ]),
    );
    return { ...outgoing, branches };
  }
  return outgoing;
}

export function renameNode(doc: EditorDocument, id: string, newId: string): CommandResult {
  if (!findNode(doc.graph, id)) return rejected('unknown-node', id);
  if (id === newId) return accepted(doc);
  if (idProblem(newId)) return rejected('invalid-id', newId);
  if (findNode(doc.graph, newId)) return rejected('duplicate-id', newId);
  const nodes = doc.graph.nodes.map((node) => ({
    ...node,
    id: node.id === id ? newId : node.id,
    outgoing: retarget(node.outgoing, id, newId),
  }));
  const layout = Object.fromEntries(
    Object.entries(doc.layout).map(([key, point]) => [key === id ? newId : key, point]),
  );
  const initialNode = doc.graph.initialNode === id ? newId : doc.graph.initialNode;
  return accepted({ graph: { ...doc.graph, nodes, initialNode }, layout });
}

export function setInitial(doc: EditorDocument, id: string): CommandResult {
  if (!findNode(doc.graph, id)) return rejected('unknown-node', id);
  if (doc.graph.initialNode === id) return accepted(doc);
  return accepted({ ...doc, graph: { ...doc.graph, initialNode: id } });
}

/** Give a node a direct output, replacing any previous direct target. */
export function connect(doc: EditorDocument, source: string, target: Target): CommandResult {
  const node = findNode(doc.graph, source);
  if (!node) return rejected('unknown-node', source);
  if (!isTarget(doc.graph, target)) return rejected('unknown-node', target);
  if (node.outgoing.kind === 'decision') return rejected('has-decision', source);
  if (node.outgoing.kind === 'direct' && node.outgoing.target === target) return accepted(doc);
  return accepted(withNode(doc, source, (n) => ({ ...n, outgoing: { kind: 'direct', target } })));
}

export function disconnect(doc: EditorDocument, source: string): CommandResult {
  const node = findNode(doc.graph, source);
  if (!node) return rejected('unknown-node', source);
  if (node.outgoing.kind === 'decision') return rejected('has-decision', source);
  if (node.outgoing.kind === 'none') return accepted(doc);
  return accepted(withNode(doc, source, (n) => ({ ...n, outgoing: { kind: 'none' } })));
}

/** Replace a node's output with a routing decision whose branches start unconnected. */
export function setDecision(
  doc: EditorDocument,
  catalog: Catalog,
  source: string,
  strategyId: string,
): CommandResult {
  const node = findNode(doc.graph, source);
  if (!node) return rejected('unknown-node', source);
  const strategy = catalog.routingStrategies.find((s) => s.identifier === strategyId);
  if (!strategy) return rejected('unknown-strategy', strategyId);
  if (node.outgoing.kind === 'decision' && node.outgoing.strategy === strategyId)
    return accepted(doc);
  const branches = Object.fromEntries(strategy.outputs.map((label) => [label, null]));
  return accepted(
    withNode(doc, source, (n) => ({
      ...n,
      outgoing: { kind: 'decision', strategy: strategyId, branches },
    })),
  );
}

export function clearDecision(doc: EditorDocument, source: string): CommandResult {
  const node = findNode(doc.graph, source);
  if (!node) return rejected('unknown-node', source);
  if (node.outgoing.kind !== 'decision') return accepted(doc);
  return accepted(withNode(doc, source, (n) => ({ ...n, outgoing: { kind: 'none' } })));
}

function branchOf(doc: EditorDocument, source: string, label: string) {
  const node = findNode(doc.graph, source);
  if (!node) return rejected('unknown-node', source);
  if (node.outgoing.kind !== 'decision') return rejected('no-decision', source);
  if (!(label in node.outgoing.branches)) return rejected('unknown-branch', label);
  return node.outgoing;
}

export function connectBranch(
  doc: EditorDocument,
  source: string,
  label: string,
  target: Target,
): CommandResult {
  const outgoing = branchOf(doc, source, label);
  if ('ok' in outgoing) return outgoing;
  if (!isTarget(doc.graph, target)) return rejected('unknown-node', target);
  if (outgoing.branches[label] === target) return accepted(doc);
  return accepted(
    withNode(doc, source, (n) => ({
      ...n,
      outgoing: { ...outgoing, branches: { ...outgoing.branches, [label]: target } },
    })),
  );
}

export function disconnectBranch(
  doc: EditorDocument,
  source: string,
  label: string,
): CommandResult {
  const outgoing = branchOf(doc, source, label);
  if ('ok' in outgoing) return outgoing;
  if (outgoing.branches[label] === null) return accepted(doc);
  return accepted(
    withNode(doc, source, (n) => ({
      ...n,
      outgoing: { ...outgoing, branches: { ...outgoing.branches, [label]: null } },
    })),
  );
}

const isFinitePoint = (point: Point) => Number.isFinite(point.x) && Number.isFinite(point.y);

/** Move nodes; used for both dragging and applying a computed layout. */
export function moveNodes(doc: EditorDocument, positions: Record<string, Point>): CommandResult {
  const entries = Object.entries(positions);
  for (const [id, point] of entries) {
    if (!findNode(doc.graph, id)) return rejected('unknown-node', id);
    if (!isFinitePoint(point)) return rejected('invalid-position', id);
  }
  const changed = entries.filter(([id, point]) => {
    const current = doc.layout[id];
    return !current || current.x !== point.x || current.y !== point.y;
  });
  if (changed.length === 0) return accepted(doc);
  return accepted({ ...doc, layout: { ...doc.layout, ...Object.fromEntries(changed) } });
}

export const applyLayout = moveNodes;

const MAX_DESCRIPTION_LENGTH = 500;
const MAX_NAME_LENGTH = 100;
/** The backend keeps this name for the built-in pipeline. */
export const RESERVED_ARCHITECTURE_NAMES: ReadonlySet<string> = new Set(['gaia_v31']);

export function setDescription(doc: EditorDocument, id: string, text: string): CommandResult {
  const node = findNode(doc.graph, id);
  if (!node) return rejected('unknown-node', id);
  if (text.length > MAX_DESCRIPTION_LENGTH) return rejected('invalid-description', id);
  if (node.description === text) return accepted(doc);
  return accepted(withNode(doc, id, (n) => ({ ...n, description: text })));
}

/** Rename the architecture itself, which decides which history a saved version joins. */
export function renameArchitecture(doc: EditorDocument, name: string): CommandResult {
  if (name === doc.graph.architectureId) return accepted(doc);
  if (name.trim() === '' || name !== name.trim() || name.length > MAX_NAME_LENGTH) {
    return rejected('invalid-name', name);
  }
  if (RESERVED_ARCHITECTURE_NAMES.has(name)) return rejected('reserved-name', name);
  return accepted({ ...doc, graph: { ...doc.graph, architectureId: name } });
}
