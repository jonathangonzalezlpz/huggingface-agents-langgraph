import type { Score } from '../../domain/history';
import type { Language } from '../../i18n';

export const formatSeconds = (seconds: number | null) =>
  seconds === null ? '—' : `${seconds.toFixed(1)} s`;

export const formatPercent = (ratio: number | null) =>
  ratio === null ? '—' : `${(ratio * 100).toFixed(1)} %`;

export const formatScore = (score: Score) => ({
  percent: score.percent.toFixed(1),
  correct: score.correct,
  attempted: score.attempted,
});

export function formatDate(value: string | null, language: Language): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(language);
}
