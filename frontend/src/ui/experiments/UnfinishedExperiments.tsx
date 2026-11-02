import { canResume } from '../../domain/battery';
import type { ExperimentRecord } from '../../domain/history';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import type { AsyncState } from '../hooks/useAsyncData';

type StoredExperiments = AsyncState<ExperimentRecord[]> & { reload: () => void };

/** Experiments that stopped before their last question, each with a way to resume it. */
export function UnfinishedExperiments({
  stored,
  canStart,
  onResume,
}: {
  stored: StoredExperiments;
  canStart: boolean;
  onResume: (experimentId: string) => void;
}) {
  const { t } = useI18n();
  const unfinished = stored.status === 'success' ? stored.data.filter(canResume) : [];

  return (
    <section aria-labelledby="unfinished-heading" className="space-y-3">
      <h2 id="unfinished-heading" className="text-lg font-semibold">
        {t('experiments.unfinished')}
      </h2>
      {stored.status === 'error' ? (
        <ErrorNotice error={stored.error} onRetry={stored.reload} />
      ) : unfinished.length === 0 ? (
        <p className="text-sm text-fg-muted">{t('experiments.unfinished.none')}</p>
      ) : (
        <>
          <p className="text-sm text-fg-muted">{t('experiments.resume.hint')}</p>
          <ul className="space-y-2">
            {unfinished.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2"
              >
                <span className="font-medium">{item.name}</span>
                <span className="text-sm text-fg-muted">
                  {t('experiments.unfinished.progress', {
                    completed: item.completed,
                    total: item.total,
                  })}
                </span>
                <button
                  type="button"
                  aria-label={t('experiments.resume.label', { name: item.name })}
                  disabled={!canStart}
                  onClick={() => onResume(item.id)}
                  className="ml-auto min-h-9 rounded-lg border border-line-strong px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t('experiments.resume')}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
