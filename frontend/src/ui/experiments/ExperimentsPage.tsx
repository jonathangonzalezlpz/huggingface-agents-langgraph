import { useCallback } from 'react';

import { isBatteryActive } from '../../domain/battery';
import { useI18n } from '../../i18n/I18nProvider';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { BatteryForm } from './BatteryForm';
import { BatteryStatusCard } from './BatteryStatusCard';
import { UnfinishedExperiments } from './UnfinishedExperiments';
import { useBattery } from './useBattery';

/** Start, follow, stop and resume batteries of GAIA questions run by the server. */
export function ExperimentsPage({ pollMs }: { pollMs?: number } = {}) {
  const { t } = useI18n();
  const { experiments, batteries, mode } = useServices();
  const live = mode === 'live';

  const stored = useAsyncData(useCallback(() => experiments.list(), [experiments]));
  const { status, loaded, busy, actionError, start, stop } = useBattery(batteries, {
    onFinished: stored.reload,
    ...(pollMs !== undefined ? { pollMs } : {}),
  });
  const active = isBatteryActive(status);

  return (
    <>
      {!live && (
        <p
          role="note"
          className="mb-4 rounded-lg border border-line-strong bg-info-soft p-3 text-sm"
        >
          {t('experiments.demo')}
        </p>
      )}
      <div className="max-w-3xl space-y-10">
        <BatteryForm
          live={live}
          loaded={loaded}
          active={active}
          busy={busy}
          error={actionError}
          onStart={(request) => void start(request)}
        />
        <BatteryStatusCard status={status} busy={busy} onStop={() => void stop()} />
        <UnfinishedExperiments
          stored={stored}
          canStart={live && !active && !busy}
          onResume={(experimentId) => void start({ kind: 'resume', experimentId })}
        />
      </div>
    </>
  );
}
