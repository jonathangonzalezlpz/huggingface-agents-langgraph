import { useCallback } from 'react';

import type { Comparison, ExperimentRecord, TaskChange } from '../../domain/history';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { formatPercent, formatSeconds } from './format';

const KNOWN_WARNINGS: Record<string, MessageKey> = {
  'The experiments do not share the same task set.': 'compare.warning.tasks',
  'The experiments were run with different code.': 'compare.warning.code',
  'Code identity is unknown for some experiments.': 'compare.warning.codeUnknown',
  'Some experiments are partial (cancelled or incomplete).': 'compare.warning.partial',
  'Some groups have a single run: no noise estimate is available.': 'compare.warning.single',
};

const CELL = 'border-b border-line px-3 py-2 text-left text-sm';
const HEAD = `${CELL} font-medium text-fg-muted`;

function Tristate({ value }: { value: boolean | null }) {
  const { t } = useI18n();
  return (
    <>{value === null ? t('compare.unknownValue') : value ? t('compare.yes') : t('compare.no')}</>
  );
}

function Outcome({
  correct,
  error,
  change,
}: {
  correct: boolean | null;
  error: boolean;
  change: TaskChange | null;
}) {
  const { t } = useI18n();
  const label =
    correct === null
      ? t('compare.outcome.unscored')
      : correct
        ? t('compare.outcome.correct')
        : t('compare.outcome.wrong');
  return (
    <span>
      {label}
      {error && ` · ${t('compare.outcome.error')}`}
      {change === 'gained' && ` · ${t('compare.change.gained')}`}
      {change === 'lost' && ` · ${t('compare.change.lost')}`}
    </span>
  );
}

function Result({
  comparison,
  records,
}: {
  comparison: Comparison;
  records: readonly ExperimentRecord[];
}) {
  const { t } = useI18n();
  const { comparability } = comparison;
  const nameOf = (id: string) => comparison.experiments.find((item) => item.id === id)?.name ?? id;
  const questionOf = (taskId: string) =>
    records.flatMap((record) => record.answers).find((answer) => answer.taskId === taskId)
      ?.question ?? taskId;

  return (
    <div className="space-y-8">
      <section aria-labelledby="groups-heading">
        <h3 id="groups-heading" className="mb-2 font-semibold">
          {t('compare.groups')}
        </h3>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead>
              <tr>
                <th className={HEAD}>{t('compare.group')}</th>
                <th className={HEAD}>{t('compare.col.runs')}</th>
                <th className={HEAD}>{t('compare.col.accuracy')}</th>
                <th className={HEAD}>{t('compare.col.mean')}</th>
                <th className={HEAD}>{t('compare.vsBase')}</th>
              </tr>
            </thead>
            <tbody>
              {comparison.groups.map((group) => {
                const base = group.key === comparison.baseGroup;
                const names = group.experimentIds.map(nameOf).join(', ');
                return (
                  <tr key={group.key}>
                    <th scope="row" className={`${CELL} font-medium`}>
                      {names}
                      {base && (
                        <span className="ml-2 text-xs text-accent-fg">
                          ({t('compare.group.base')})
                        </span>
                      )}
                    </th>
                    <td className={CELL}>{group.runs}</td>
                    <td className={CELL}>
                      {group.accuracy ? formatPercent(group.accuracy.mean) : '—'}
                    </td>
                    <td className={CELL}>
                      {group.meanSeconds ? formatSeconds(group.meanSeconds.mean) : '—'}
                    </td>
                    <td className={CELL}>
                      {group.versusBase ? (
                        <ul className="space-y-0.5">
                          <li>
                            {t('compare.gained')}: {group.versusBase.gained} · {t('compare.lost')}:{' '}
                            {group.versusBase.lost} · {t('compare.unchanged')}:{' '}
                            {group.versusBase.unchanged}
                            {group.versusBase.unknown > 0 &&
                              ` · ${t('compare.unknown')}: ${group.versusBase.unknown}`}
                          </li>
                          {group.versusBase.accuracyDelta !== null && (
                            <li>
                              {t('compare.delta')}:{' '}
                              {(group.versusBase.accuracyDelta * 100).toFixed(1)} pp
                            </li>
                          )}
                          {group.versusBase.meanSecondsDelta !== null && (
                            <li>
                              {t('compare.seconds')}: {group.versusBase.meanSecondsDelta.toFixed(1)}{' '}
                              s
                            </li>
                          )}
                          <li className="text-fg-muted">
                            {t(`compare.assessment.${group.versusBase.assessment}` as MessageKey)}
                          </li>
                        </ul>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="per-experiment-heading">
        <h3 id="per-experiment-heading" className="mb-2 font-semibold">
          {t('compare.col.experiments')}
        </h3>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead>
              <tr>
                <th className={HEAD}>{t('history.col.name')}</th>
                <th className={HEAD}>{t('compare.col.accuracy')}</th>
                <th className={HEAD}>{t('compare.col.mean')}</th>
                <th className={HEAD}>{t('compare.col.median')}</th>
                <th className={HEAD}>{t('compare.col.p95')}</th>
                <th className={HEAD}>{t('compare.col.errors')}</th>
                <th className={HEAD}>{t('compare.col.truncated')}</th>
              </tr>
            </thead>
            <tbody>
              {comparison.experiments.map((item) => (
                <tr key={item.id}>
                  <th scope="row" className={`${CELL} font-medium`}>
                    {item.name}
                  </th>
                  <td className={CELL}>
                    {formatPercent(item.metrics.accuracy)}
                    {item.metrics.correct !== null &&
                      ` (${item.metrics.correct}/${item.metrics.answered})`}
                  </td>
                  <td className={CELL}>{formatSeconds(item.metrics.meanSeconds)}</td>
                  <td className={CELL}>{formatSeconds(item.metrics.medianSeconds)}</td>
                  <td className={CELL}>{formatSeconds(item.metrics.p95Seconds)}</td>
                  <td className={CELL}>{item.metrics.technicalErrors}</td>
                  <td className={CELL}>{item.metrics.truncatedCalls}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="comparability-heading" className="space-y-2">
        <h3 id="comparability-heading" className="font-semibold">
          {t('compare.comparability')}
        </h3>
        <ul className="text-sm">
          <li>
            {t('compare.same.tasks')}: <Tristate value={comparability.sameTaskSet} />
          </li>
          <li>
            {t('compare.same.code')}: <Tristate value={comparability.sameCode} />
          </li>
          <li>
            {t('compare.same.architecture')}: <Tristate value={comparability.sameArchitecture} />
          </li>
          <li>
            {comparability.configDifferences.length === 0
              ? t('compare.noConfigDiffs')
              : t('compare.configDiffs', { fields: comparability.configDifferences.join(', ') })}
          </li>
        </ul>
        {comparability.warnings.length > 0 && (
          <div role="note" className="rounded-lg border border-line-strong bg-warning-soft p-3">
            <p className="text-sm font-medium">{t('compare.warnings')}</p>
            <ul className="list-disc pl-5 text-sm">
              {comparability.warnings.map((warning) => {
                const key = KNOWN_WARNINGS[warning];
                return <li key={warning}>{key ? t(key) : warning}</li>;
              })}
            </ul>
          </div>
        )}
      </section>

      <section aria-labelledby="tasks-heading">
        <h3 id="tasks-heading" className="mb-2 font-semibold">
          {t('compare.tasks')}
        </h3>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[40rem] border-collapse">
            <thead>
              <tr>
                <th className={HEAD}>{t('compare.task')}</th>
                {comparison.experiments.map((item) => (
                  <th key={item.id} className={HEAD}>
                    {item.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparison.tasks.map((task) => (
                <tr key={task.taskId}>
                  <th scope="row" className={`${CELL} max-w-xs font-normal`}>
                    <span className="line-clamp-2">{questionOf(task.taskId)}</span>
                  </th>
                  {comparison.experiments.map((item) => {
                    const outcome = task.outcomes[item.id];
                    return (
                      <td key={item.id} className={CELL}>
                        {outcome ? (
                          <Outcome
                            correct={outcome.correct}
                            error={outcome.error}
                            change={outcome.versusBase}
                          />
                        ) : (
                          '—'
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/** Ask the server to compare the chosen experiments and show what came back. */
export function ComparisonView({
  ids,
  base,
  records,
}: {
  ids: string[];
  base: string | null;
  records: readonly ExperimentRecord[];
}) {
  const { t } = useI18n();
  const { experiments } = useServices();
  const key = ids.join('|');
  // The ids are joined into a stable key so the request only repeats when the choice changes.
  const load = useCallback(
    () => experiments.compare({ ids: key.split('|'), base }),
    [experiments, key, base],
  );
  const state = useAsyncData(load);

  return (
    <section aria-labelledby="comparison-heading" className="space-y-4">
      <h2 id="comparison-heading" className="text-lg font-semibold">
        {t('compare.title')}
      </h2>
      {state.status === 'loading' && <p className="text-fg-muted">{t('compare.loading')}</p>}
      {state.status === 'error' && <ErrorNotice error={state.error} onRetry={state.reload} />}
      {state.status === 'success' && <Result comparison={state.data} records={records} />}
    </section>
  );
}
