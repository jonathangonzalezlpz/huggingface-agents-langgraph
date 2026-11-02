import { ArrowLeft } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { StudioError } from '../../domain/errors';
import {
  canEvaluateLocally,
  canSubmitOfficially,
  type ExperimentAnswer,
  type ExperimentRecord,
} from '../../domain/history';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useAsyncData } from '../hooks/useAsyncData';
import { AttachmentLink } from '../run/GaiaPicker';
import { useServices } from '../services';
import { formatDate, formatScore, formatSeconds } from './format';
import { ArchitectureLabel, ExperimentStatus } from './HistoryPage';
import { OfficialSubmitDialog } from './OfficialSubmitDialog';

const CELL = 'border-b border-line px-3 py-2 text-left text-sm align-top';
const HEAD = `${CELL} font-medium text-fg-muted`;
const BUTTON =
  'inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50';

function Result({ answer }: { answer: ExperimentAnswer }) {
  const { t } = useI18n();
  if (answer.locallyCorrect === null) {
    return <span className="text-fg-muted">{t('detail.result.unscored')}</span>;
  }
  return answer.locallyCorrect ? (
    <span className="text-success">{t('detail.result.correct')}</span>
  ) : (
    <span className="text-error">{t('detail.result.wrong')}</span>
  );
}

function Scoring({ record, onChanged }: { record: ExperimentRecord; onChanged: () => void }) {
  const { t } = useI18n();
  const { experiments } = useServices();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<MessageKey | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const evaluate = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await experiments.evaluate(record.id);
      onChanged();
    } catch (error) {
      const unavailable = error instanceof StudioError && error.status === 503;
      setFailure(unavailable ? 'score.local.unavailable' : 'score.local.failed');
    } finally {
      setBusy(false);
    }
  };

  const complete = canEvaluateLocally(record);
  return (
    <section aria-labelledby="score-heading" className="space-y-3">
      <h3 id="score-heading" className="font-semibold">
        {t('score.title')}
      </h3>
      <dl className="grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs font-medium text-fg-muted">{t('score.local')}</dt>
          <dd className="mt-0.5 text-sm">
            {record.localScore
              ? t('history.score.value', formatScore(record.localScore))
              : t('score.none')}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-fg-muted">{t('score.official')}</dt>
          <dd className="mt-0.5 text-sm">
            {record.officialScore
              ? t('history.score.value', formatScore(record.officialScore))
              : t('score.none')}
          </dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={BUTTON}
          disabled={!complete || busy}
          onClick={() => void evaluate()}
        >
          {busy ? t('score.local.running') : t('score.local.run')}
        </button>
        <button
          type="button"
          className={BUTTON}
          disabled={!canSubmitOfficially(record)}
          onClick={() => setDialogOpen(true)}
        >
          {record.officialScore ? t('official.done') : t('official.run')}
        </button>
      </div>
      <p className="text-xs text-fg-muted">
        {complete ? t('score.local.hint') : t('score.local.needs')}
      </p>
      {failure && (
        <p role="alert" className="text-sm text-error">
          {t(failure)}
        </p>
      )}

      <OfficialSubmitDialog
        record={record}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSent={onChanged}
      />
    </section>
  );
}

export function ExperimentDetailPage() {
  const { t, language } = useI18n();
  const { experiments } = useServices();
  const { id = '' } = useParams();
  const state = useAsyncData(useCallback(() => experiments.list(), [experiments]));

  const back = (
    <Link
      to="/experiments/history"
      className="mb-4 inline-flex items-center gap-1.5 text-sm text-accent-fg underline underline-offset-2"
    >
      <ArrowLeft aria-hidden="true" className="size-4" />
      {t('detail.back')}
    </Link>
  );

  if (state.status === 'loading') return <p className="text-fg-muted">{t('common.loading')}</p>;
  if (state.status === 'error') return <ErrorNotice error={state.error} onRetry={state.reload} />;
  const record = state.data.find((item) => item.id === id);
  if (!record) {
    return (
      <>
        {back}
        <p>{t('detail.notFound')}</p>
      </>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        {back}
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">{record.name}</h2>
          <ExperimentStatus status={record.status} />
        </div>
        <dl className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs font-medium text-fg-muted">{t('history.col.version')}</dt>
            <dd className="mt-0.5 text-sm">{record.pipelineVersion ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-fg-muted">{t('history.col.architecture')}</dt>
            <dd className="mt-0.5 text-sm">
              <ArchitectureLabel value={record.architecture} />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-fg-muted">{t('history.col.time')}</dt>
            <dd className="mt-0.5 text-sm">{formatSeconds(record.averageSeconds)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-fg-muted">{t('history.col.date')}</dt>
            <dd className="mt-0.5 text-sm">{formatDate(record.createdAt, language)}</dd>
          </div>
        </dl>
      </div>

      <Scoring record={record} onChanged={state.reload} />

      <section aria-labelledby="answers-heading">
        <h3 id="answers-heading" className="mb-2 font-semibold">
          {t('detail.answers')}
        </h3>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[48rem] border-collapse">
            <thead>
              <tr>
                <th className={HEAD}>{t('detail.col.question')}</th>
                <th className={HEAD}>{t('detail.col.answer')}</th>
                <th className={HEAD}>{t('detail.col.route')}</th>
                <th className={HEAD}>{t('detail.col.time')}</th>
                <th className={HEAD}>{t('detail.col.result')}</th>
                <th className={HEAD}>
                  <span className="sr-only">{t('detail.viewRun')}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {record.answers.map((answer) => (
                <tr key={answer.taskId}>
                  <td className={`${CELL} max-w-sm`}>
                    <span className="line-clamp-3">{answer.question}</span>
                  </td>
                  <td className={CELL}>
                    {answer.answer || <span className="text-fg-muted">{t('detail.noAnswer')}</span>}
                    {answer.fileName && <AttachmentLink taskId={answer.taskId} />}
                    {answer.error && (
                      <p className="mt-1 text-xs text-error">
                        {t('detail.error', { message: answer.error })}
                      </p>
                    )}
                  </td>
                  <td className={CELL}>{answer.route || '—'}</td>
                  <td className={CELL}>{formatSeconds(answer.durationSeconds)}</td>
                  <td className={CELL}>
                    <Result answer={answer} />
                  </td>
                  <td className={CELL}>
                    {answer.runId ? (
                      <Link
                        to={`/runs/${encodeURIComponent(answer.runId)}`}
                        className="text-accent-fg underline underline-offset-2"
                      >
                        {t('detail.viewRun')}
                      </Link>
                    ) : (
                      <span className="text-fg-muted">{t('detail.noRun')}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
