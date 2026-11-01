import { z } from 'zod';

import { checkInvariants, type EditorDocument } from '../../domain/editor/model';
import type { DraftPort, DraftSummary, SavedMarker } from '../../ports';

const STORAGE_KEY = 'studio.drafts.v1';
const MAX_DRAFTS = 20;

const pointSchema = z.object({ x: z.number(), y: z.number() });

const outgoingSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('none') }),
  z.object({ kind: z.literal('direct'), target: z.string() }),
  z.object({
    kind: z.literal('decision'),
    strategy: z.string(),
    branches: z.record(z.string(), z.string().nullable()),
  }),
]);

const documentSchema = z.object({
  graph: z.object({
    architectureId: z.string(),
    schemaVersion: z.string(),
    stateType: z.string(),
    initialNode: z.string().nullable(),
    nodes: z.array(
      z.object({
        id: z.string(),
        implementationId: z.string(),
        description: z.string(),
        outgoing: outgoingSchema,
      }),
    ),
  }),
  layout: z.record(z.string(), pointSchema),
});

const markerSchema = z.object({
  versionId: z.string(),
  version: z.number().int(),
  definitionJson: z.string(),
});

const storeSchema = z.object({
  version: z.literal(1),
  drafts: z.array(
    z.object({
      id: z.string(),
      updatedAt: z.number(),
      document: documentSchema,
      saved: markerSchema.optional(),
    }),
  ),
});

type Stored = z.output<typeof storeSchema>['drafts'];

/** Drafts kept in this browser. Unreadable or inconsistent data is discarded, never trusted. */
export function createLocalStorageDrafts(
  storage: Storage = localStorage,
  now: () => number = () => Date.now(),
): DraftPort {
  function read(): Stored {
    try {
      const raw = storage.getItem(STORAGE_KEY);
      if (raw === null) return [];
      const parsed = storeSchema.safeParse(JSON.parse(raw));
      if (!parsed.success) return [];
      return parsed.data.drafts.filter(
        (draft) => checkInvariants(draft.document as EditorDocument).length === 0,
      );
    } catch {
      return [];
    }
  }

  function write(drafts: Stored): void {
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, drafts }));
    } catch {
      // A full or blocked storage must not break editing; the draft simply is not kept.
    }
  }

  const newestFirst = (drafts: Stored) => [...drafts].sort((a, b) => b.updatedAt - a.updatedAt);

  return {
    list(): DraftSummary[] {
      return newestFirst(read()).map((draft) => ({
        id: draft.id,
        architectureId: draft.document.graph.architectureId,
        nodeCount: draft.document.graph.nodes.length,
        updatedAt: draft.updatedAt,
      }));
    },
    load: (id) => (read().find((draft) => draft.id === id)?.document as EditorDocument) ?? null,
    save(id, document) {
      const drafts = read();
      const saved = drafts.find((draft) => draft.id === id)?.saved;
      const entry = { id, updatedAt: now(), document, ...(saved ? { saved } : {}) };
      write(
        newestFirst([...drafts.filter((draft) => draft.id !== id), entry]).slice(0, MAX_DRAFTS),
      );
    },
    remove(id) {
      write(read().filter((draft) => draft.id !== id));
    },
    markSaved(id, marker) {
      const drafts = read();
      if (!drafts.some((draft) => draft.id === id)) return;
      write(drafts.map((draft) => (draft.id === id ? { ...draft, saved: marker } : draft)));
    },
    savedMarker: (id): SavedMarker | null => read().find((draft) => draft.id === id)?.saved ?? null,
  };
}
