import { Graph, layout } from '@dagrejs/dagre';

import {
  END,
  targetsOf,
  type EditorGraph,
  type EditorNode,
  type Point,
} from '../../domain/editor/model';

export const NODE_WIDTH = 240;
const BASE_HEIGHT = 84;
const BRANCH_ROW_HEIGHT = 26;
const START = '__start__';

/** Height of a node card: decisions add one row per branch. */
export function nodeHeight(node: EditorNode): number {
  return node.outgoing.kind === 'decision'
    ? BASE_HEIGHT + Object.keys(node.outgoing.branches).length * BRANCH_ROW_HEIGHT
    : BASE_HEIGHT;
}

/**
 * Layered left-to-right positions (top-left corners) for every node.
 * The start and end markers take part in the layering but are not returned: the canvas
 * places them next to the entry and the last layer by itself.
 */
export function computeLayout(graph: EditorGraph): Record<string, Point> {
  if (graph.nodes.length === 0) return {};
  const g = new Graph();
  g.setGraph({ rankdir: 'LR', nodesep: 56, ranksep: 100, marginx: 32, marginy: 32 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of graph.nodes)
    g.setNode(node.id, { width: NODE_WIDTH, height: nodeHeight(node) });
  g.setNode(START, { width: 72, height: 40 });
  g.setNode(END, { width: 72, height: 40 });
  if (graph.initialNode) g.setEdge(START, graph.initialNode);
  for (const node of graph.nodes) {
    for (const target of new Set(targetsOf(node.outgoing))) g.setEdge(node.id, target);
  }

  layout(g);

  const positions: Record<string, Point> = {};
  for (const node of graph.nodes) {
    const placed = g.node(node.id);
    positions[node.id] = {
      x: Math.round(placed.x - NODE_WIDTH / 2),
      y: Math.round(placed.y - nodeHeight(node) / 2),
    };
  }
  return positions;
}
