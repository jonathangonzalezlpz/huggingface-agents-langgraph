import {
  blankDocument,
  linearDocument,
  documentFromArchitecture,
} from '../../domain/editor/templates';
import type { EditorDocument } from '../../domain/editor/model';
import type { Architecture, Catalog } from '../../domain/types';
import { toDefinition } from '../../domain/editor/convert';
import type { SavedMarker, StudioServices } from '../../ports';
import { computeLayout } from './autoLayout';

export type DraftKind = 'blank' | 'linear' | 'copy';

const DEFAULT_NAME = 'my_agent';

export function newDraftId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `draft-${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}

/** A name not used by any existing draft, derived from `base`. */
export function uniqueArchitectureId(base: string, taken: readonly string[]): string {
  if (!taken.includes(base)) return base;
  for (let n = 2; ; n += 1) {
    if (!taken.includes(`${base}_${n}`)) return `${base}_${n}`;
  }
}

/** Lay out a document whose nodes have no stored positions yet. */
function withLayout(doc: EditorDocument): EditorDocument {
  return { ...doc, layout: computeLayout(doc.graph) };
}

export function buildDraft(
  kind: DraftKind,
  catalog: Catalog,
  taken: readonly string[],
  source?: Architecture,
): EditorDocument {
  const name = uniqueArchitectureId(
    kind === 'copy' ? `${source?.architectureId ?? DEFAULT_NAME}_copy` : DEFAULT_NAME,
    taken,
  );
  if (kind === 'blank') return blankDocument(name);
  if (kind === 'linear') return withLayout(linearDocument(name, catalog));
  if (!source) throw new Error('A copy needs a source architecture');
  return withLayout(documentFromArchitecture(source, catalog, name));
}

/** Save a new local draft and return its id. */
export function saveNewDraft(services: StudioServices, doc: EditorDocument): string {
  const id = newDraftId();
  services.drafts.save(id, doc);
  return id;
}

/**
 * Begin editing a version. A saved version keeps its name, so saving the draft creates the next
 * version of the same architecture; the built-in pipeline keeps a reserved name and is copied
 * under a new one. Returns the id of the new draft.
 */
export async function startEditing(
  services: StudioServices,
  architecture: Architecture,
): Promise<string> {
  const [catalog, stored] = await Promise.all([
    services.catalog.getCatalog(),
    services.layouts.get(architecture.id).catch(() => ({})),
  ]);
  const taken = services.drafts.list().map((draft) => draft.architectureId);
  const sameName = !architecture.readOnly;
  const name = sameName
    ? architecture.architectureId
    : uniqueArchitectureId(`${architecture.architectureId}_copy`, taken);
  const base = documentFromArchitecture(architecture, catalog, name, stored);
  const doc =
    Object.keys(stored).length > 0 ? base : { ...base, layout: computeLayout(base.graph) };
  const id = saveNewDraft(services, doc);
  if (sameName) {
    const marker: SavedMarker = {
      versionId: architecture.id,
      version: architecture.version ?? 0,
      definitionJson: JSON.stringify(toDefinition(doc.graph)),
    };
    services.drafts.markSaved(id, marker);
  }
  return id;
}
