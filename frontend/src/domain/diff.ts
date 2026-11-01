import type { AgentDefinition, EdgeDefinition } from './types';

export interface DefinitionDiff {
  nodesAdded: string[];
  nodesRemoved: string[];
  /** Nodes whose component or description changed. */
  nodesChanged: string[];
  edgesAdded: string[];
  edgesRemoved: string[];
  entryChanged: boolean;
  isEmpty: boolean;
}

const END_ALIASES = new Set(['__end__', 'END']);
const label = (target: string) => (END_ALIASES.has(target) ? 'end' : target);

/** One readable line per connection, so a diff is a plain difference of sets. */
function edgeLines(edge: EdgeDefinition): string[] {
  if (edge.type === 'direct') return [`${edge.source} → ${label(edge.target)}`];
  return [
    `${edge.source} ⟡ ${edge.routingStrategy}`,
    ...Object.entries(edge.branches).map(
      ([branch, target]) => `${edge.source} [${branch}] → ${label(target)}`,
    ),
  ];
}

const linesOf = (definition: AgentDefinition) =>
  new Set(definition.edges.flatMap((edge) => edgeLines(edge)));

const only = (from: Set<string>, other: Set<string>) =>
  [...from].filter((item) => !other.has(item)).sort();

/** What changed between two versions of an architecture. Its own name is not a change. */
export function diffDefinitions(before: AgentDefinition, after: AgentDefinition): DefinitionDiff {
  const previous = new Map(before.nodes.map((node) => [node.id, node]));
  const next = new Map(after.nodes.map((node) => [node.id, node]));

  const nodesAdded = [...next.keys()].filter((id) => !previous.has(id)).sort();
  const nodesRemoved = [...previous.keys()].filter((id) => !next.has(id)).sort();
  const nodesChanged = [...next.keys()]
    .filter((id) => {
      const a = previous.get(id);
      const b = next.get(id);
      return (
        a && b && (a.implementationId !== b.implementationId || a.description !== b.description)
      );
    })
    .sort();

  const beforeEdges = linesOf(before);
  const afterEdges = linesOf(after);
  const edgesAdded = only(afterEdges, beforeEdges);
  const edgesRemoved = only(beforeEdges, afterEdges);
  const entryChanged = before.initialNode !== after.initialNode;

  return {
    nodesAdded,
    nodesRemoved,
    nodesChanged,
    edgesAdded,
    edgesRemoved,
    entryChanged,
    isEmpty:
      !entryChanged &&
      [nodesAdded, nodesRemoved, nodesChanged, edgesAdded, edgesRemoved].every(
        (l) => l.length === 0,
      ),
  };
}
