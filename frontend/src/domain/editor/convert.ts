import type { AgentDefinition, Catalog, EdgeDefinition } from '../types';
import {
  END,
  SCHEMA_VERSION,
  STATE_TYPE,
  type EditorGraph,
  type EditorNode,
  type Outgoing,
} from './model';

const START_ALIASES = new Set(['__start__', 'START']);
const END_ALIASES = new Set(['__end__', 'END']);

export interface ConversionIssue {
  code: 'multiple-outgoing' | 'unknown-source' | 'unknown-initial';
  nodeId: string;
}

const normalize = (target: string) => (END_ALIASES.has(target) ? END : target);

/**
 * Build the editable graph from a stored definition. Anything the editor cannot
 * represent (a node with several outputs, edges from nowhere) is reported, never hidden.
 */
export function fromDefinition(
  definition: AgentDefinition,
  catalog: Catalog,
): { graph: EditorGraph; issues: ConversionIssue[] } {
  const issues: ConversionIssue[] = [];
  const outgoing = new Map<string, Outgoing>();

  for (const edge of definition.edges) {
    if (START_ALIASES.has(edge.source)) continue;
    if (!definition.nodes.some((node) => node.id === edge.source)) {
      issues.push({ code: 'unknown-source', nodeId: edge.source });
      continue;
    }
    if (outgoing.has(edge.source)) {
      issues.push({ code: 'multiple-outgoing', nodeId: edge.source });
      continue;
    }
    if (edge.type === 'direct') {
      outgoing.set(edge.source, { kind: 'direct', target: normalize(edge.target) });
    } else {
      const outputs = catalog.routingStrategies.find(
        (s) => s.identifier === edge.routingStrategy,
      )?.outputs;
      const branches: Record<string, string | null> = Object.fromEntries(
        (outputs ?? []).map((label) => [label, null]),
      );
      for (const [label, target] of Object.entries(edge.branches))
        branches[label] = normalize(target);
      outgoing.set(edge.source, { kind: 'decision', strategy: edge.routingStrategy, branches });
    }
  }

  const nodes: EditorNode[] = definition.nodes.map((node) => ({
    id: node.id,
    implementationId: node.implementationId,
    description: node.description,
    outgoing: outgoing.get(node.id) ?? { kind: 'none' },
  }));
  const entryExists = nodes.some((node) => node.id === definition.initialNode);
  if (!entryExists && nodes.length > 0)
    issues.push({ code: 'unknown-initial', nodeId: definition.initialNode });

  return {
    graph: {
      architectureId: definition.architectureId,
      schemaVersion: definition.schemaVersion || SCHEMA_VERSION,
      stateType: definition.stateType || STATE_TYPE,
      initialNode: entryExists ? definition.initialNode : (nodes[0]?.id ?? null),
      nodes,
    },
    issues,
  };
}

/**
 * Serialize for the backend. Unconnected branches are left out, so the validator reports
 * the incomplete decision; a decision with no connected branch cannot be stored at all.
 */
export function toDefinition(graph: EditorGraph): AgentDefinition {
  const edges: EdgeDefinition[] = [];
  for (const node of graph.nodes) {
    const { outgoing } = node;
    if (outgoing.kind === 'direct') {
      edges.push({ type: 'direct', source: node.id, target: outgoing.target });
    } else if (outgoing.kind === 'decision') {
      const branches = Object.fromEntries(
        Object.entries(outgoing.branches).filter(
          (entry): entry is [string, string] => entry[1] !== null,
        ),
      );
      if (Object.keys(branches).length > 0) {
        edges.push({
          type: 'conditional',
          source: node.id,
          routingStrategy: outgoing.strategy,
          branches,
        });
      }
    }
  }
  return {
    schemaVersion: graph.schemaVersion,
    architectureId: graph.architectureId,
    stateType: graph.stateType,
    initialNode: graph.initialNode ?? '',
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      implementationId: node.implementationId,
      description: node.description,
    })),
    edges,
  };
}
