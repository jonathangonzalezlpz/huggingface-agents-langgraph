/**
 * The editable graph. Its shape makes the backend's structural rules unrepresentable
 * rather than merely forbidden: a node has at most one output (direct or a decision),
 * and nothing can target the start of the graph.
 */

/** Terminal target meaning "the run ends here". */
export const END = '__end__';

export const RESERVED_IDS: ReadonlySet<string> = new Set(['__start__', '__end__', 'START', 'END']);
export const MAX_ID_LENGTH = 100;

export interface Point {
  x: number;
  y: number;
}

/** A node id, or END. */
export type Target = string;

export type Outgoing =
  | { kind: 'none' }
  | { kind: 'direct'; target: Target }
  /** A routing decision: one branch per label of the strategy, null while unconnected. */
  | { kind: 'decision'; strategy: string; branches: Record<string, Target | null> };

export interface EditorNode {
  id: string;
  implementationId: string;
  description: string;
  outgoing: Outgoing;
}

export interface EditorGraph {
  architectureId: string;
  schemaVersion: string;
  stateType: string;
  /** Entry point; null only while the graph has no nodes. */
  initialNode: string | null;
  nodes: EditorNode[];
}

/** The graph plus where each node sits on the canvas. Layout is not part of identity. */
export interface EditorDocument {
  graph: EditorGraph;
  layout: Record<string, Point>;
}

export const SCHEMA_VERSION = '4.0';
export const STATE_TYPE = 'AgentState';

export function findNode(graph: EditorGraph, id: string): EditorNode | undefined {
  return graph.nodes.find((node) => node.id === id);
}

/** Why an id cannot name a node, or null when it is acceptable. */
export function idProblem(id: string): string | null {
  if (id.trim() === '' || id !== id.trim()) return 'blank or padded';
  if (id.length > MAX_ID_LENGTH) return 'too long';
  if (RESERVED_IDS.has(id)) return 'reserved';
  return null;
}

export function targetsOf(outgoing: Outgoing): Target[] {
  if (outgoing.kind === 'direct') return [outgoing.target];
  if (outgoing.kind === 'decision') {
    return Object.values(outgoing.branches).filter((target): target is Target => target !== null);
  }
  return [];
}

/** Every rule the model promises; an empty list means the document is consistent. */
export function checkInvariants(doc: EditorDocument): string[] {
  const { graph, layout } = doc;
  const problems: string[] = [];
  const ids = graph.nodes.map((node) => node.id);
  const known = new Set(ids);

  if (known.size !== ids.length) problems.push('duplicate node ids');
  for (const id of ids) {
    const problem = idProblem(id);
    if (problem) problems.push(`node id "${id}" is ${problem}`);
  }
  if (graph.nodes.length === 0 && graph.initialNode !== null) problems.push('entry without nodes');
  if (graph.nodes.length > 0 && (graph.initialNode === null || !known.has(graph.initialNode))) {
    problems.push('entry is not a node');
  }
  for (const node of graph.nodes) {
    for (const target of targetsOf(node.outgoing)) {
      if (target !== END && !known.has(target))
        problems.push(`${node.id} targets unknown "${target}"`);
    }
  }
  for (const id of Object.keys(layout)) {
    if (!known.has(id)) problems.push(`layout for unknown node "${id}"`);
  }
  return problems;
}
