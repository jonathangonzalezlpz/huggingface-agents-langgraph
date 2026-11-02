import { Loader2, Play } from 'lucide-react';

import { useI18n } from '../../i18n/I18nProvider';

/** Start a run, and while it works, how long it has taken and a way to stop waiting. */
export function RunControls({
  canRun,
  running,
  elapsed,
  onRun,
  onStopWaiting,
}: {
  canRun: boolean;
  running: boolean;
  elapsed: number;
  onRun: () => void;
  onStopWaiting: () => void;
}) {
  const { t } = useI18n();
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={!canRun}
          onClick={onRun}
          className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <Play aria-hidden="true" className="size-4" />
          )}
          {running ? t('runs.running', { seconds: elapsed }) : t('runs.run')}
        </button>
        {running && (
          <button
            type="button"
            onClick={onStopWaiting}
            className="min-h-10 rounded-lg border border-line-strong px-3 text-sm font-medium"
          >
            {t('runs.stopWaiting')}
          </button>
        )}
      </div>
      {running && <p className="text-sm text-fg-muted">{t('runs.running.hint')}</p>}
    </>
  );
}
