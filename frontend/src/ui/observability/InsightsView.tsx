import { useCallback } from 'react';

import type { Insights } from '../../domain/insights';
import { batteryExports } from '../../domain/trace';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatPercent, formatSeconds } from '../experiments/format';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { ExportLinks } from './ExportLinks';

const CELL = 'border-b border-line px-3 py-2 text-left text-sm';
const HEAD = `${CELL} font-medium text-fg-muted`;

function Totals({ insights }: { insights: Insights }) {
  const { t } = useI18n();
  const { totals } = insights;
  const items: [MessageKey, string][] = [
    ['obs.insights.accuracy', formatPercent(totals.accuracy)],
    ['obs.insights.mean', formatSeconds(totals.meanSeconds)],
    ['obs.insights.tokens', String(totals.completionTokens)],
    ['obs.insights.errors', String(totals.technicalErrors)],
  ];
  return (
    <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs font-medium text-fg-muted">{t(label)}</dt>
          <dd className="mt-0.5 text-lg font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Stages({ insights }: { insights: Insights }) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="stages-heading">
      <h3 id="stages-heading" className="mb-2 font-semibold">
        {t('obs.insights.stages')}
      </h3>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[30rem] border-collapse">
          <thead>
            <tr>
              <th className={HEAD}>{t('obs.insights.stage')}</th>
              <th className={HEAD}>{t('obs.insights.total')}</th>
              <th className={HEAD}>{t('obs.insights.perTask')}</th>
              <th className={HEAD}>{t('obs.insights.share')}</th>
            </tr>
          </thead>
          <tbody>
            {insights.stages.map((stage) => (
              <tr key={stage.stage}>
                <td className={CELL}>{stage.stage}</td>
                <td className={CELL}>{formatSeconds(stage.totalSeconds)}</td>
                <td className={CELL}>{formatSeconds(stage.meanSeconds)}</td>
                <td className={CELL}>
                  <span className="flex items-center gap-2">
                    <span aria-hidden="true" className="h-2 w-24 rounded bg-muted">
                      <span
                        className="block h-2 rounded bg-accent"
                        style={{ width: `${Math.round(stage.share * 100)}%` }}
                      />
                    </span>
                    {formatPercent(stage.share)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Routes({ insights }: { insights: Insights }) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="routes-heading">
      <h3 id="routes-heading" className="mb-2 font-semibold">
        {t('obs.insights.routes')}
      </h3>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[30rem] border-collapse">
          <thead>
            <tr>
              <th className={HEAD}>{t('obs.insights.route')}</th>
              <th className={HEAD}>{t('obs.insights.count')}</th>
              <th className={HEAD}>{t('obs.insights.correct')}</th>
              <th className={HEAD}>{t('obs.insights.accuracy')}</th>
              <th className={HEAD}>{t('obs.insights.mean')}</th>
            </tr>
          </thead>
          <tbody>
            {insights.routes.map((route) => (
              <tr key={route.route}>
                <td className={CELL}>{route.route}</td>
                <td className={CELL}>{route.count}</td>
                <td className={CELL}>{route.correct}</td>
                <td className={CELL}>{formatPercent(route.accuracy)}</td>
                <td className={CELL}>{formatSeconds(route.meanSeconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Failures({ insights }: { insights: Insights }) {
  const { t } = useI18n();
  const { failures, slowestTasks } = insights;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section aria-labelledby="failures-heading" className="space-y-1 text-sm">
        <h3 id="failures-heading" className="mb-2 font-semibold">
          {t('obs.insights.failures')}
        </h3>
        <p>{t('obs.insights.wrong', { count: failures.wrongAnswers })}</p>
        <p>{t('obs.insights.truncated', { count: failures.truncatedCalls })}</p>
        {failures.errors.length === 0 ? (
          <p className="text-fg-muted">{t('obs.insights.noErrors')}</p>
        ) : (
          <ul className="list-disc pl-5">
            {failures.errors.map((error) => (
              <li key={error.message}>
                {t('obs.insights.errorCount', { message: error.message, count: error.count })}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="slowest-heading" className="text-sm">
        <h3 id="slowest-heading" className="mb-2 font-semibold">
          {t('obs.insights.slowest')}
        </h3>
        <ul className="list-disc pl-5">
          {slowestTasks.map((task) => (
            <li key={task.taskId}>
              {t('obs.insights.slowestItem', {
                task: task.taskId,
                time: formatSeconds(task.durationSeconds),
                stage: task.slowestStage ?? '—',
              })}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** Where time goes, which routes fail and why, for one stored battery. */
export function InsightsView({ experimentId }: { experimentId: string }) {
  const { t } = useI18n();
  const { traces } = useServices();
  const state = useAsyncData(
    useCallback(() => traces.getInsights(experimentId), [traces, experimentId]),
  );
  if (state.status === 'loading') {
    return <p className="text-fg-muted">{t('obs.insights.loading')}</p>;
  }
  if (state.status === 'error') return <ErrorNotice error={state.error} onRetry={state.reload} />;
  const insights = state.data;
  if (insights.totals.answered === 0) {
    return <p className="text-fg-muted">{t('obs.insights.empty')}</p>;
  }
  return (
    <div className="space-y-6">
      <Totals insights={insights} />
      <ExportLinks links={batteryExports(experimentId)} />
      <Stages insights={insights} />
      <Routes insights={insights} />
      <Failures insights={insights} />
    </div>
  );
}
