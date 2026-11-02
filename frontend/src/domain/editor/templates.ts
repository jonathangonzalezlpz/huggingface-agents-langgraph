import type { Architecture, Catalog, ParamValue } from '../types';
import {
  addNode,
  connect,
  connectBranch,
  setDecision,
  setParam,
  uniqueNodeId,
  type CommandResult,
} from './commands';
import { fromDefinition } from './convert';
import { END, SCHEMA_VERSION, STATE_TYPE, type EditorDocument, type Point } from './model';

/** Gap between nodes of the generated templates, before any automatic layout. */
const TEMPLATE_SPACING = 280;

export function blankDocument(architectureId: string): EditorDocument {
  return {
    graph: {
      architectureId,
      schemaVersion: SCHEMA_VERSION,
      stateType: STATE_TYPE,
      initialNode: null,
      nodes: [],
    },
    layout: {},
  };
}

const LINEAR_PIPELINE = ['preprocessing', 'reasoning', 'answer_production'] as const;

/** The smallest runnable pipeline: preprocess, reason, produce the answer. */
export function linearDocument(architectureId: string, catalog: Catalog): EditorDocument {
  let doc = blankDocument(architectureId);
  LINEAR_PIPELINE.forEach((component, index) => {
    const position: Point = { x: index * TEMPLATE_SPACING, y: 0 };
    const added = addNode(doc, catalog, component, position);
    if (!added.ok) throw new Error(`The catalog has no component "${component}"`);
    doc = added.doc;
  });
  for (const [index, source] of LINEAR_PIPELINE.entries()) {
    const target = LINEAR_PIPELINE[index + 1] ?? END;
    const linked = connect(doc, source, target);
    if (!linked.ok) throw new Error(`Cannot connect "${source}"`);
    doc = linked.doc;
  }
  return doc;
}

/** An editable copy of an existing architecture under a new name. */
export function documentFromArchitecture(
  architecture: Architecture,
  catalog: Catalog,
  architectureId: string,
  layout: Record<string, Point> = {},
): EditorDocument {
  const { graph } = fromDefinition(architecture.definition, catalog);
  const known = new Set(graph.nodes.map((node) => node.id));
  return {
    graph: { ...graph, architectureId },
    layout: Object.fromEntries(Object.entries(layout).filter(([id]) => known.has(id))),
  };
}

/** Templates are built from the same commands as the editor, so they can never be invalid. */
function must(result: CommandResult, what: string): EditorDocument {
  if (!result.ok) throw new Error(`Template step failed (${what}): ${result.reason.code}`);
  return result.doc;
}

interface Step {
  id: string;
  component: string;
  params?: Record<string, ParamValue>;
}

/** Append nodes after the document's end, giving each a fresh id and the listed parameters. */
function addSteps(doc: EditorDocument, catalog: Catalog, steps: readonly Step[], at: Point) {
  let current = doc;
  const ids: string[] = [];
  steps.forEach((step, index) => {
    const id = uniqueNodeId(current.graph, step.id);
    current = must(
      addNode(
        current,
        catalog,
        step.component,
        { x: at.x + index * TEMPLATE_SPACING, y: at.y },
        id,
      ),
      `add ${step.component}`,
    );
    for (const [name, value] of Object.entries(step.params ?? {})) {
      current = must(setParam(current, catalog, id, name, value), `set ${name}`);
    }
    ids.push(id);
  });
  return { doc: current, ids };
}

function chain(doc: EditorDocument, ids: readonly string[]): EditorDocument {
  let current = doc;
  ids.forEach((id, index) => {
    current = must(connect(current, id, ids[index + 1] ?? END), `connect ${id}`);
  });
  return current;
}

/**
 * The V3.1 pipeline with a verification loop before the answer is formatted: the reasoning goes
 * to a verifier, which either accepts or sends the draft to a reflection step and back.
 */
export function verifiedDocument(
  architectureId: string,
  catalog: Catalog,
  base: Architecture,
): EditorDocument {
  const original = documentFromArchitecture(base, catalog, architectureId);
  const { doc, ids } = addSteps(
    original,
    catalog,
    [
      { id: 'verify', component: 'llm_verifier', params: { max_revisions: 1 } },
      { id: 'revise', component: 'llm_reflect' },
    ],
    { x: 0, y: 0 },
  );
  const [verify, revise] = ids as [string, string];
  let current = must(connect(doc, 'reasoning', verify), 'connect reasoning');
  current = must(setDecision(current, catalog, verify, 'route_on_verdict'), 'decide');
  current = must(connectBranch(current, verify, 'accept', 'answer_production'), 'accept');
  current = must(connectBranch(current, verify, 'revise', revise), 'revise');
  return must(connect(current, revise, verify), 'loop back');
}

/** Plan the task, gather evidence with a tool, then reason and answer. */
export function plannedDocument(architectureId: string, catalog: Catalog): EditorDocument {
  const { doc, ids } = addSteps(
    blankDocument(architectureId),
    catalog,
    [
      { id: 'preprocessing', component: 'preprocessing' },
      { id: 'plan', component: 'llm_planner' },
      { id: 'search', component: 'web_search' },
      { id: 'reasoning', component: 'reasoning' },
      { id: 'answer_production', component: 'answer_production' },
    ],
    { x: 0, y: 0 },
  );
  return chain(doc, ids);
}

/** Search once, sample several answers and keep the majority, then format it. */
export function consistencyDocument(architectureId: string, catalog: Catalog): EditorDocument {
  const { doc, ids } = addSteps(
    blankDocument(architectureId),
    catalog,
    [
      { id: 'preprocessing', component: 'preprocessing' },
      { id: 'search', component: 'web_search' },
      { id: 'vote', component: 'self_consistency', params: { n: 3 } },
      { id: 'answer_production', component: 'answer_production' },
    ],
    { x: 0, y: 0 },
  );
  return chain(doc, ids);
}
