import { END } from './editor/model';
import type { RunStep } from './run';

export interface NodeVisit {
  visits: number;
  seconds: number;
  failed: boolean;
  /** Index of the first step that reached this node. */
  firstStep: number;
}

/** How each node took part in the first `upTo` steps. Loops show up as repeated visits. */
export function visitsByNode(
  steps: readonly RunStep[],
  upTo = steps.length,
): Map<string, NodeVisit> {
  const visits = new Map<string, NodeVisit>();
  steps.slice(0, upTo).forEach((step, index) => {
    const current = visits.get(step.node);
    visits.set(step.node, {
      visits: (current?.visits ?? 0) + 1,
      seconds: (current?.seconds ?? 0) + step.durationSeconds,
      failed: (current?.failed ?? false) || step.error !== null,
      firstStep: current?.firstStep ?? index,
    });
  });
  return visits;
}

/**
 * Connections the run went through, as `source->target`. The end is reached only when the run
 * completed, every step was replayed and the last one did not fail.
 */
export function traversedEdges(
  steps: readonly RunStep[],
  upTo: number,
  completed: boolean,
): Set<string> {
  const shown = steps.slice(0, upTo);
  const edges = new Set<string>();
  shown.forEach((step, index) => {
    const next = shown[index + 1];
    if (next) edges.add(`${step.node}->${next.node}`);
  });
  const last = shown.at(-1);
  if (last && completed && upTo >= steps.length && last.error === null) {
    edges.add(`${last.node}->${END}`);
  }
  return edges;
}

export function failedStep(steps: readonly RunStep[]): RunStep | null {
  return steps.find((step) => step.error !== null) ?? null;
}
