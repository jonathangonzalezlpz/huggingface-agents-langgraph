/** Aggregates over one battery: where time goes, which routes fail and why. */

export type TaskOutcome = 'correct' | 'wrong' | 'error' | 'unscored';

export interface InsightTotals {
  answered: number;
  scored: number;
  correct: number;
  accuracy: number | null;
  meanSeconds: number | null;
  completionTokens: number;
  technicalErrors: number;
}

export interface RouteInsight {
  route: string;
  count: number;
  scored: number;
  correct: number;
  accuracy: number | null;
  meanSeconds: number | null;
}

export interface StageInsight {
  stage: string;
  totalSeconds: number;
  meanSeconds: number;
  tasks: number;
  /** Fraction of all recorded stage time, from 0 to 1. */
  share: number;
}

export interface Insights {
  totals: InsightTotals;
  routes: RouteInsight[];
  stages: StageInsight[];
  failures: {
    wrongAnswers: number;
    errors: { message: string; count: number }[];
    truncatedCalls: number;
  };
  tasks: { taskId: string; outcome: TaskOutcome }[];
  slowestTasks: { taskId: string; durationSeconds: number; slowestStage: string | null }[];
}
