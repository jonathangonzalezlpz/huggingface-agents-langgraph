import type { ExperimentSummary } from './battery';

export interface Score {
  /** Percentage, 0 to 100. */
  percent: number;
  correct: number;
  attempted: number;
}

export interface ExperimentAnswer {
  taskId: string;
  question: string;
  fileName: string;
  answer: string;
  error: string;
  route: string;
  durationSeconds: number | null;
  runId: string | null;
  /** Null until the experiment has been scored locally. */
  locallyCorrect: boolean | null;
}

/** A stored experiment with what the history and detail views show. */
export interface ExperimentRecord extends ExperimentSummary {
  answers: ExperimentAnswer[];
  localScore: Score | null;
  officialScore: Score | null;
}

export const QUESTION_COUNT = 20;

/** Scoring needs every question answered. */
export const isComplete = (record: ExperimentRecord) => record.answers.length === QUESTION_COUNT;

export const canEvaluateLocally = (record: ExperimentRecord) => isComplete(record);

/** The official evaluator is only offered for a complete experiment not yet submitted. */
export const canSubmitOfficially = (record: ExperimentRecord) =>
  isComplete(record) && record.officialScore === null;

export const isTechnicalError = (answer: ExperimentAnswer) => answer.error !== '';

export type HistorySort = 'newest' | 'score' | 'speed';

/** Newest first, best local score first, or fastest first; unknown values go last. */
export function sortHistory(
  records: readonly ExperimentRecord[],
  sort: HistorySort,
): ExperimentRecord[] {
  const key = (record: ExperimentRecord): number => {
    if (sort === 'score') return -(record.localScore?.percent ?? -1);
    if (sort === 'speed') return record.averageSeconds ?? Number.POSITIVE_INFINITY;
    return -Date.parse(record.createdAt ?? '') || 0;
  };
  return [...records].sort((a, b) => key(a) - key(b));
}

export function filterHistory(records: readonly ExperimentRecord[], query: string) {
  const needle = query.trim().toLowerCase();
  if (needle === '') return [...records];
  return records.filter((record) =>
    [record.name, record.architecture ?? '', record.pipelineVersion ?? '', record.status].some(
      (text) => text.toLowerCase().includes(needle),
    ),
  );
}

export interface Range {
  min: number;
  max: number;
  mean: number;
}

export type ChangeCounts = Record<'gained' | 'lost' | 'unchanged' | 'unknown', number>;

export interface ComparedExperiment {
  id: string;
  name: string;
  status: string;
  group: string;
  metrics: {
    answered: number;
    correct: number | null;
    accuracy: number | null;
    meanSeconds: number | null;
    medianSeconds: number | null;
    p95Seconds: number | null;
    technicalErrors: number;
    truncatedCalls: number;
  };
}

export interface ComparedGroup {
  key: string;
  experimentIds: string[];
  runs: number;
  accuracy: Range | null;
  meanSeconds: Range | null;
  versusBase:
    | (ChangeCounts & {
        accuracyDelta: number | null;
        assessment: string;
        meanSecondsDelta: number | null;
      })
    | null;
}

export type TaskChange = 'gained' | 'lost' | 'unchanged' | 'unknown';

export interface TaskOutcome {
  correct: boolean | null;
  route: string | null;
  seconds: number | null;
  error: boolean;
  versusBase: TaskChange | null;
}

export interface Comparison {
  baseGroup: string;
  experiments: ComparedExperiment[];
  groups: ComparedGroup[];
  comparability: {
    sameTaskSet: boolean;
    sameCode: boolean | null;
    sameArchitecture: boolean;
    configDifferences: string[];
    warnings: string[];
  };
  tasks: { taskId: string; outcomes: Record<string, TaskOutcome> }[];
}

export const MIN_COMPARED = 2;
export const MAX_COMPARED = 20;

export interface OfficialSubmission {
  experimentId: string;
  username: string;
  agentCode: string;
}

/** What the confirmation shows before anything leaves the machine. */
export interface SubmissionPreview {
  username: string;
  agentCode: string;
  answers: number;
}

export function submissionIssue(username: string, agentCode: string): 'username' | 'code' | null {
  if (username.trim() === '') return 'username';
  if (agentCode.trim() === '') return 'code';
  return null;
}
