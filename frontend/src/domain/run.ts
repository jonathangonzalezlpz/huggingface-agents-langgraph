/** What running an architecture needs and returns. Independent of how the backend encodes it. */

export interface RunStep {
  /** The id of the node that ran. */
  node: string;
  durationSeconds: number;
  error: string | null;
  /** Names of the state fields the step wrote. */
  updatedFields: string[];
}

export interface RunArchitecture {
  engine: string;
  id: string | null;
  version: number | null;
  contentSha256: string | null;
}

export type RunStatus = 'completed' | 'error';

export interface RunRecord {
  id: string;
  status: RunStatus;
  durationSeconds: number;
  steps: RunStep[];
  architecture: RunArchitecture | null;
  question: string;
  answer: string | null;
  route: string | null;
  error: string | null;
  modelId: string | null;
}

export interface ModelOption {
  provider: 'configured' | 'ollama';
  modelId: string;
}

export interface GaiaQuestion {
  taskId: string;
  question: string;
  fileName: string;
  level: string;
}

import type { ExperimentSettings } from './experiment';

export interface RunRequest {
  /** A saved version (or the built-in pipeline). */
  architectureId: string;
  question: string;
  taskId: string;
  /** Empty when the question has no attachment. */
  fileName: string;
  settings: ExperimentSettings;
}
