/** Outbound ports: what the Studio needs from the outside world. */
import type { EditorDocument, Point } from '../domain/editor/model';
import type {
  AgentDefinition,
  Architecture,
  ArchitectureSummary,
  Catalog,
  SystemStatus,
  ValidationReport,
} from '../domain/types';

export interface CatalogPort {
  getCatalog(): Promise<Catalog>;
}

export interface SaveResult {
  architecture: Architecture;
  /** False when identical content was already stored, so no new version was created. */
  created: boolean;
}

export interface ArchitecturePort {
  list(): Promise<ArchitectureSummary[]>;
  get(id: string): Promise<Architecture>;
  /** Store a definition as a new immutable version. Rejects with kind `unavailable` in demo mode. */
  save(definition: AgentDefinition): Promise<SaveResult>;
}

export interface SystemPort {
  getStatus(): Promise<SystemStatus>;
}

export interface ValidationPort {
  /** Static analysis of a definition. Rejects with kind `unavailable` where it cannot run. */
  validate(definition: AgentDefinition): Promise<ValidationReport>;
}

/** Where nodes sit on the canvas, kept per architecture version and apart from its identity. */
export interface LayoutPort {
  get(architectureId: string): Promise<Record<string, Point>>;
  save(architectureId: string, positions: Record<string, Point>): Promise<void>;
}

export interface DraftSummary {
  id: string;
  architectureId: string;
  nodeCount: number;
  updatedAt: number;
}

/** Which saved version a draft last became, to tell whether it changed since. */
export interface SavedMarker {
  versionId: string;
  version: number;
  /** The definition as saved, serialized canonically for comparison. */
  definitionJson: string;
}

/** Work in progress that is not a saved version yet. Local to this browser. */
export interface DraftPort {
  list(): DraftSummary[];
  load(id: string): EditorDocument | null;
  /** Keeps the saved marker, if any. */
  save(id: string, document: EditorDocument): void;
  remove(id: string): void;
  markSaved(id: string, marker: SavedMarker): void;
  savedMarker(id: string): SavedMarker | null;
}

export type StudioMode = 'live' | 'demo';

export interface StudioServices {
  mode: StudioMode;
  catalog: CatalogPort;
  architectures: ArchitecturePort;
  system: SystemPort;
  validation: ValidationPort;
  layouts: LayoutPort;
  drafts: DraftPort;
}
