import type { ExperimentSettings, PipelineVersion } from './experiment';

export type BatteryState = 'idle' | 'running' | 'stopping' | 'completed' | 'cancelled' | 'failed';

export interface BatteryStatus {
  state: BatteryState;
  experimentId: string | null;
  name: string | null;
  completed: number;
  total: number;
  error: string | null;
  startedAt: string | null;
}

export const IDLE_BATTERY: BatteryStatus = {
  state: 'idle',
  experimentId: null,
  name: null,
  completed: 0,
  total: 0,
  error: null,
  startedAt: null,
};

/** A battery is in progress and the server will keep working on it. */
export const isBatteryActive = (status: BatteryStatus) =>
  status.state === 'running' || status.state === 'stopping';

/** Start a new battery, or continue an unfinished experiment (which keeps its own settings). */
export type BatteryRequest =
  | { kind: 'new'; settings: ExperimentSettings; architectureId: string; limit: number }
  | { kind: 'resume'; experimentId: string };

/** A stored experiment as the lists need it. Answers and per-task detail stay on the server. */
export interface ExperimentSummary {
  id: string;
  status: string;
  name: string;
  pipelineVersion: PipelineVersion | null;
  architecture: string | null;
  completed: number;
  total: number;
  createdAt: string | null;
  averageSeconds: number | null;
}

/** Unfinished experiments can continue where they stopped. */
export const canResume = (experiment: ExperimentSummary) =>
  experiment.status !== 'completed' && experiment.completed < experiment.total;

/** Fraction done, 0 to 1; zero when the size is not known yet. */
export function batteryProgress(status: BatteryStatus): number {
  return status.total > 0 ? Math.min(status.completed / status.total, 1) : 0;
}
