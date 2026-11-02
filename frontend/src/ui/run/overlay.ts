import type { Edge } from '@xyflow/react';

import type { RunStep } from '../../domain/run';
import { traversedEdges, visitsByNode } from '../../domain/runPath';
import {
  START_ID,
  type ComponentFlowNode,
  type FlowNode,
  type NodeRunState,
} from '../editor/projection';

export interface RunView {
  steps: readonly RunStep[];
  /** How many steps are shown: all of them, or fewer during a replay. */
  position: number;
  completed: boolean;
}

const MUTED = 0.22;

/**
 * Draw a run over a projected graph: which nodes took part, the one active now, where it
 * failed, and which connections were followed. The projection itself is left untouched.
 */
export function applyRunOverlay(
  projected: { nodes: FlowNode[]; edges: Edge[] },
  view: RunView,
): { nodes: FlowNode[]; edges: Edge[] } {
  const visits = visitsByNode(view.steps, view.position);
  const active = view.steps[view.position - 1]?.node ?? null;
  const taken = traversedEdges(view.steps, view.position, view.completed);

  const nodes = projected.nodes.map((node): FlowNode => {
    if (node.type !== 'component') return node;
    const visit = visits.get(node.id);
    const state: NodeRunState['state'] = !visit
      ? 'skipped'
      : visit.failed
        ? 'failed'
        : node.id === active
          ? 'active'
          : 'visited';
    const run: NodeRunState = {
      state,
      visits: visit?.visits ?? 0,
      seconds: visit?.seconds ?? 0,
    };
    return { ...node, data: { ...node.data, run } } as ComponentFlowNode;
  });

  const edges = projected.edges.map((edge): Edge => {
    const followed =
      edge.source === START_ID ? view.position > 0 : taken.has(`${edge.source}->${edge.target}`);
    return {
      ...edge,
      style: followed
        ? { ...edge.style, stroke: 'var(--accent)', strokeWidth: 2.8 }
        : { ...edge.style, opacity: MUTED },
      selectable: false,
      focusable: false,
    };
  });

  return { nodes, edges };
}
