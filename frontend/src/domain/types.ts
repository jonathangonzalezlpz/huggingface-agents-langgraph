/** Domain model of the Studio. Framework-free and independent of the wire format. */

export type Severity = 'error' | 'warning' | 'info';

export interface Diagnostic {
  code: string;
  severity: Severity;
  message: string;
  nodeId?: string;
  edgeSource?: string;
  branch?: string;
}

/** Fields present when a node starts: on every path, or only on some. */
export interface NodeAvailability {
  guaranteed: string[];
  possible: string[];
}

export interface ValidationReport {
  isValid: boolean;
  counts: Record<Severity, number>;
  diagnostics: Diagnostic[];
  availability: Record<string, NodeAvailability>;
}

export type Category = 'input' | 'acquisition' | 'research' | 'reasoning' | 'output' | 'other';

export interface NodeContract {
  requiredInputs: string[];
  optionalInputs: string[];
  guaranteedOutputs: string[];
  optionalOutputs: string[];
}

export interface ComponentInfo {
  implementationId: string;
  description: string;
  category: Category;
  recoverErrors: boolean;
  contract: NodeContract;
}

export interface RoutingStrategyInfo {
  identifier: string;
  description: string;
  outputs: string[];
}

export interface Catalog {
  categories: Category[];
  components: ComponentInfo[];
  routingStrategies: RoutingStrategyInfo[];
  state: { types: string[]; fields: string[]; initialFields: string[] };
}

export interface NodeDefinition {
  id: string;
  implementationId: string;
  description: string;
}

export type EdgeDefinition =
  | { type: 'direct'; source: string; target: string }
  | {
      type: 'conditional';
      source: string;
      routingStrategy: string;
      branches: Record<string, string>;
    };

export interface AgentDefinition {
  schemaVersion: string;
  architectureId: string;
  stateType: string;
  initialNode: string;
  nodes: NodeDefinition[];
  edges: EdgeDefinition[];
}

export interface ArchitectureSummary {
  id: string;
  architectureId: string;
  /** Null for the built-in pipeline, which is not a stored version. */
  version: number | null;
  parentId: string | null;
  contentSha256: string;
  createdAt: string | null;
  readOnly: boolean;
}

export interface Architecture extends ArchitectureSummary {
  definition: AgentDefinition;
  validation: ValidationReport;
}

export type LlmState = 'ready' | 'sleeping' | 'loading' | 'unavailable';

export interface SystemStatus {
  backend: 'online' | 'offline';
  /** Null when the backend could not report the model state. */
  llm: { state: LlmState; name: string } | null;
  /** Null when the backend did not report the graphics card. */
  gpu: { available: boolean; name: string | null; backend: string | null } | null;
  /** Null when the backend did not report host memory. */
  hostMemory: { availableMib: number; totalMib: number } | null;
}
