/** Outbound ports: what the Studio needs from the outside world. */
import type { BatteryRequest, BatteryStatus } from '../domain/battery';
import type { Comparison, ExperimentRecord, OfficialSubmission, Score } from '../domain/history';
import type { EditorDocument, Point } from '../domain/editor/model';
import type { GaiaQuestion, ModelCatalog, RunRecord, RunRequest } from '../domain/run';
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

export interface RunPort {
  /**
   * Run a saved version and return its record. A run that fails midway is still a record (with
   * status `error` and the steps that happened); only a refusal before it started rejects.
   */
  run(request: RunRequest, signal?: AbortSignal): Promise<RunRecord>;
  get(id: string): Promise<RunRecord>;
}

export interface BatteryPort {
  /** Start a battery or resume an experiment. Rejects with status 409 if one is running. */
  start(request: BatteryRequest): Promise<BatteryStatus>;
  current(): Promise<BatteryStatus>;
  /** Finish after the question in progress; the server cannot interrupt a question. */
  stop(): Promise<BatteryStatus>;
}

export interface ExperimentPort {
  /** Every stored experiment, with its answers. */
  list(): Promise<ExperimentRecord[]>;
  remove(id: string): Promise<void>;
  /** Score a complete experiment locally; the server stores the result on the record. */
  evaluate(id: string): Promise<Score>;
  /**
   * Send a stored experiment to the official evaluator. This publishes to an external service:
   * only call it after an explicit confirmation from the user.
   */
  submitOfficial(submission: OfficialSubmission): Promise<{ score: Score; saved: boolean }>;
  compare(request: { ids: string[]; base: string | null }): Promise<Comparison>;
}

export interface ModelPort {
  list(): Promise<ModelCatalog>;
}

export interface QuestionPort {
  /** Benchmark questions. Rejects with kind `unavailable` where they must not be offered. */
  list(): Promise<GaiaQuestion[]>;
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
  runs: RunPort;
  models: ModelPort;
  questions: QuestionPort;
  batteries: BatteryPort;
  experiments: ExperimentPort;
}
