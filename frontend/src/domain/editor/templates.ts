import type { Architecture, Catalog } from '../types';
import { addNode, connect } from './commands';
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
