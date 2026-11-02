import { MarkerType, type Edge, type Node } from '@xyflow/react';

import { END, type EditorDocument, type EditorNode, type Point } from '../../domain/editor/model';
import type { Catalog, ComponentInfo, Diagnostic, Severity } from '../../domain/types';
import { computeLayout, nodeHeight, NODE_WIDTH } from './autoLayout';

export const START_ID = '__start__';
export const END_ID = END;
export const OUTPUT_HANDLE = 'out';
export const INPUT_HANDLE = 'in';
export const BRANCH_PREFIX = 'branch:';

const TERMINAL_WIDTH = 72;
const TERMINAL_HEIGHT = 40;
const TERMINAL_GAP = 90;

/** How a node took part in a run being shown. */
export type NodeRunState = {
  state: 'visited' | 'skipped' | 'failed' | 'active';
  visits: number;
  seconds: number;
};

export type ComponentNodeData = {
  node: EditorNode;
  component: ComponentInfo | undefined;
  isEntry: boolean;
  /** Worst diagnostic attached to the node, if any. */
  severity: Severity | null;
  diagnosticCount: number;
  /** Null outside a run. */
  run: NodeRunState | null;
};
export type TerminalNodeData = { kind: 'start' | 'end' };

export type ComponentFlowNode = Node<ComponentNodeData, 'component'>;
export type TerminalFlowNode = Node<TerminalNodeData, 'terminal'>;
export type FlowNode = ComponentFlowNode | TerminalFlowNode;

const SEVERITY_RANK: Record<Severity, number> = { error: 3, warning: 2, info: 1 };

export const branchHandle = (label: string) => `${BRANCH_PREFIX}${label}`;

/** The label a handle id carries, or null for the plain output handle. */
export function branchOfHandle(handle: string | null | undefined): string | null {
  return handle?.startsWith(BRANCH_PREFIX) ? handle.slice(BRANCH_PREFIX.length) : null;
}

function worstByNode(
  diagnostics: Diagnostic[],
): Map<string, { severity: Severity; count: number }> {
  const result = new Map<string, { severity: Severity; count: number }>();
  for (const item of diagnostics) {
    const id = item.nodeId ?? item.edgeSource;
    if (!id) continue;
    const current = result.get(id);
    const worse = !current || SEVERITY_RANK[item.severity] > SEVERITY_RANK[current.severity];
    result.set(id, {
      severity: worse ? item.severity : (current?.severity ?? item.severity),
      count: (current?.count ?? 0) + 1,
    });
  }
  return result;
}

/** Where the canvas draws a node: a live drag wins over the stored layout, then a computed one. */
function positionsFor(doc: EditorDocument, dragging: Record<string, Point>): Record<string, Point> {
  const missing = doc.graph.nodes.some((node) => !doc.layout[node.id]);
  const computed = missing ? computeLayout(doc.graph) : {};
  return Object.fromEntries(
    doc.graph.nodes.map((node) => [
      node.id,
      dragging[node.id] ?? doc.layout[node.id] ?? computed[node.id] ?? { x: 0, y: 0 },
    ]),
  );
}

const edgeStyle = { stroke: 'var(--text-muted)', strokeWidth: 1.6 };
const marker = { type: MarkerType.ArrowClosed, color: 'var(--text-muted)' } as const;

/** Translate the editable document into React Flow nodes and edges. */
export function projectGraph(
  doc: EditorDocument,
  catalog: Catalog,
  diagnostics: Diagnostic[] = [],
  dragging: Record<string, Point> = {},
): { nodes: FlowNode[]; edges: Edge[] } {
  const positions = positionsFor(doc, dragging);
  const worst = worstByNode(diagnostics);
  const components = new Map(catalog.components.map((c) => [c.implementationId, c]));

  const nodes: FlowNode[] = doc.graph.nodes.map((node) => {
    const attached = worst.get(node.id);
    return {
      id: node.id,
      type: 'component',
      position: positions[node.id] ?? { x: 0, y: 0 },
      data: {
        node,
        component: components.get(node.implementationId),
        isEntry: doc.graph.initialNode === node.id,
        severity: attached?.severity ?? null,
        diagnosticCount: attached?.count ?? 0,
        run: null,
      },
      width: NODE_WIDTH,
      height: nodeHeight(node),
      ariaLabel: node.id,
    };
  });

  const placed = doc.graph.nodes.map((node) => positions[node.id] ?? { x: 0, y: 0 });
  const entry = doc.graph.nodes.find((node) => node.id === doc.graph.initialNode);
  const entryPosition = entry ? (positions[entry.id] ?? { x: 0, y: 0 }) : null;

  if (entry && entryPosition) {
    nodes.push({
      id: START_ID,
      type: 'terminal',
      position: {
        x: entryPosition.x - TERMINAL_WIDTH - TERMINAL_GAP,
        y: entryPosition.y + nodeHeight(entry) / 2 - TERMINAL_HEIGHT / 2,
      },
      data: { kind: 'start' },
      draggable: false,
      selectable: false,
      deletable: false,
    });
  }
  if (placed.length > 0) {
    const right = Math.max(...placed.map((p) => p.x)) + NODE_WIDTH + TERMINAL_GAP;
    const top = Math.min(...placed.map((p) => p.y));
    const bottom = Math.max(...placed.map((p) => p.y));
    nodes.push({
      id: END_ID,
      type: 'terminal',
      position: { x: right, y: (top + bottom) / 2 },
      data: { kind: 'end' },
      draggable: false,
      selectable: false,
      deletable: false,
    });
  }

  const edges: Edge[] = [];
  if (entry) {
    edges.push({
      id: `${START_ID}->${entry.id}`,
      source: START_ID,
      target: entry.id,
      targetHandle: INPUT_HANDLE,
      type: 'smoothstep',
      style: { ...edgeStyle, strokeDasharray: '2 5' },
      markerEnd: marker,
      selectable: false,
      deletable: false,
      focusable: false,
    });
  }
  for (const node of doc.graph.nodes) {
    const { outgoing } = node;
    if (outgoing.kind === 'direct') {
      edges.push({
        id: `${node.id}:${OUTPUT_HANDLE}->${outgoing.target}`,
        source: node.id,
        sourceHandle: OUTPUT_HANDLE,
        target: outgoing.target,
        targetHandle: INPUT_HANDLE,
        type: 'smoothstep',
        style: edgeStyle,
        markerEnd: marker,
      });
    } else if (outgoing.kind === 'decision') {
      for (const [label, target] of Object.entries(outgoing.branches)) {
        if (target === null) continue;
        edges.push({
          id: `${node.id}:${branchHandle(label)}->${target}`,
          source: node.id,
          sourceHandle: branchHandle(label),
          target,
          targetHandle: INPUT_HANDLE,
          type: 'smoothstep',
          label,
          style: edgeStyle,
          markerEnd: marker,
          labelStyle: { fill: 'var(--text)', fontSize: 11, fontWeight: 600 },
          labelBgStyle: { fill: 'var(--surface)' },
          labelBgPadding: [6, 3],
          labelBgBorderRadius: 4,
        });
      }
    }
  }
  return { nodes, edges };
}
