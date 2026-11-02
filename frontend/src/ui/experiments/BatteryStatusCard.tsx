import { Square } from 'lucide-react';

import {
  batteryProgress,
  isBatteryActive,
  type BatteryState,
  type BatteryStatus,
} from '../../domain/battery';
import { useI18n } from '../../i18n/I18nProvider';
import { StatusBadge, type Tone } from '../components/StatusBadge';

const STATE_TONE: Record<BatteryState, Tone> = {
  idle: 'neutral',
  running: 'info',
  stopping: 'warning',
  completed: 'success',
  cancelled: 'warning',
  failed: 'error',
};

function Progress({ status }: { status: BatteryStatus }) {
  const { t } = useI18n();
  return (
    <div>
      <progress
        aria-label={t('experiments.progress.label')}
        value={status.completed}
        max={Math.max(status.total, 1)}
        className="h-2 w-full"
      />
      <p className="mt-1 text-sm text-fg-muted">
        {t('experiments.progress', { completed: status.completed, total: status.total })} (
        {Math.round(batteryProgress(status) * 100)} %)
      </p>
    </div>
  );
}

/** The battery the server is running, or ran last: state, progress and how to stop it. */
export function BatteryStatusCard({
  status,
  busy,
  onStop,
}: {
  status: BatteryStatus;
  busy: boolean;
  onStop: () => void;
}) {
  const { t } = useI18n();
  const active = isBatteryActive(status);
  return (
    <section aria-labelledby="current-heading" className="space-y-3">
      <h2 id="current-heading" className="text-lg font-semibold">
        {t('experiments.current')}
      </h2>
      {status.state === 'idle' ? (
        <p className="text-sm text-fg-muted">{t('experiments.noCurrent')}</p>
      ) : (
        <div className="space-y-3 rounded-xl border border-line bg-surface p-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-medium">{status.name ?? status.experimentId}</span>
            <StatusBadge tone={STATE_TONE[status.state]}>
              {t(`experiments.state.${status.state}`)}
            </StatusBadge>
            {active && (
              <button
                type="button"
                disabled={busy || status.state === 'stopping'}
                onClick={onStop}
                className="ml-auto inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Square aria-hidden="true" className="size-4" />
                {t('experiments.stop')}
              </button>
            )}
          </div>
          <Progress status={status} />
          {status.state === 'stopping' && (
            <p role="status" className="text-sm text-warning">
              {t('experiments.stopping')}
            </p>
          )}
          {status.error && (
            <p role="alert" className="text-sm text-error">
              {status.error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
