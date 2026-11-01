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

export interface ArchitecturePort {
  list(): Promise<ArchitectureSummary[]>;
  get(id: string): Promise<Architecture>;
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

/** Work in progress that is not a saved version yet. Local to this browser. */
export interface DraftPort {
  list(): DraftSummary[];
  load(id: string): EditorDocument | null;
  save(id: string, document: EditorDocument): void;
  remove(id: string): void;
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
