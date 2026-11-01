import { Loader2, Play, Square } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import { loadLibrary } from '../../application/loadLibrary';
import {
  batteryProgress,
  canResume,
  isBatteryActive,
  type BatteryState,
} from '../../domain/battery';
import { StudioError } from '../../domain/errors';
import { defaultSettings, settingsIssues } from '../../domain/experiment';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge, type Tone } from '../components/StatusBadge';
import { useAsyncData } from '../hooks/useAsyncData';
import { SettingsPanel } from '../run/SettingsPanel';
import { useServices } from '../services';
import { useBattery } from './useBattery';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';
const MAX_QUESTIONS = 20;

const STATE_TONE: Record<BatteryState, Tone> = {
  idle: 'neutral',
  running: 'info',
  stopping: 'warning',
  completed: 'success',
  cancelled: 'warning',
  failed: 'error',
};

function ActionError({ error }: { error: unknown }) {
  const { t } = useI18n();
  if (error instanceof StudioError && error.kind === 'http') {
    if (error.status === 409) return <p role="alert">{t('experiments.error.busy')}</p>;
    if (error.status === 503) return <p role="alert">{t('experiments.error.unavailable')}</p>;
    if (error.status === 400) return <p role="alert">{t('experiments.error.rejected')}</p>;
  }
  return <ErrorNotice error={error} />;
}

export function ExperimentsPage({ pollMs }: { pollMs?: number } = {}) {
  const { t } = useI18n();
  const { architectures, models, experiments, batteries, mode } = useServices();
  const live = mode === 'live';

  const library = useAsyncData(useCallback(() => loadLibrary(architectures), [architectures]));
  const modelList = useAsyncData(useCallback(() => models.list(), [models]));
  const stored = useAsyncData(useCallback(() => experiments.list(), [experiments]));
  const { reload: reloadStored } = stored;

  const { status, loaded, busy, actionError, start, stop } = useBattery(batteries, {
    onFinished: reloadStored,
    ...(pollMs !== undefined ? { pollMs } : {}),
  });

  const [settings, setSettings] = useState(defaultSettings);
  const [architectureId, setArchitectureId] = useState('');
  const [limit, setLimit] = useState(MAX_QUESTIONS);

  const available = useMemo(
    () => (library.status === 'success' ? library.data.filter((a) => a.validation.isValid) : []),
    [library],
  );
  const options = modelList.status === 'success' ? modelList.data : [];
  const active = isBatteryActive(status);
  const limitValid = Number.isInteger(limit) && limit >= 1 && limit <= MAX_QUESTIONS;
  const canStart =
    live &&
    loaded &&
    !active &&
    !busy &&
    architectureId !== '' &&
    limitValid &&
    settingsIssues(settings).length === 0;
  const unfinished = stored.status === 'success' ? stored.data.filter(canResume) : [];
  const showStatus = status.state !== 'idle';

  return (
    <>
      <PageHeader title={t('experiments.title')} description={t('experiments.description')} />

      {!live && (
        <p
          role="note"
          className="mb-4 rounded-lg border border-line-strong bg-info-soft p-3 text-sm"
        >
          {t('experiments.demo')}
        </p>
      )}

      <div className="max-w-3xl space-y-10">
        <section aria-labelledby="battery-heading" className="space-y-4">
          <div>
            <h2 id="battery-heading" className="text-lg font-semibold">
              {t('experiments.battery')}
            </h2>
            <p className="text-sm text-fg-muted">{t('experiments.battery.hint')}</p>
            <p className="text-sm text-fg-muted">{t('experiments.battery.cost')}</p>
          </div>

          <div>
            <label htmlFor="battery-architecture" className="mb-1 block text-sm font-medium">
              {t('runs.architecture')}
            </label>
            {library.status === 'error' ? (
              <ErrorNotice error={library.error} onRetry={library.reload} />
            ) : (
              <select
                id="battery-architecture"
                className={FIELD}
                value={architectureId}
                disabled={active}
                onChange={(event) => setArchitectureId(event.target.value)}
              >
                <option value="">{t('runs.architecture.placeholder')}</option>
                {available.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.version === null
                      ? t('runs.architecture.builtin', { name: item.architectureId })
                      : t('runs.architecture.version', {
                          name: item.architectureId,
                          version: item.version,
                        })}
                  </option>
                ))}
              </select>
            )}
          </div>

          <SettingsPanel
            settings={settings}
            models={options}
            disabled={active}
            onChange={setSettings}
          />

          <div>
            <label htmlFor="battery-limit" className="mb-1 block text-sm font-medium">
              {t('experiments.limit')}
            </label>
            <input
              id="battery-limit"
              type="number"
              min={1}
              max={MAX_QUESTIONS}
              className={`${FIELD} max-w-32`}
              value={Number.isNaN(limit) ? '' : limit}
              disabled={active}
              onChange={(event) =>
                setLimit(event.target.value.trim() === '' ? Number.NaN : Number(event.target.value))
              }
            />
            <p className="mt-1 text-xs text-fg-muted">{t('experiments.limit.hint')}</p>
          </div>

          <button
            type="button"
            disabled={!canStart}
            onClick={() => void start({ kind: 'new', settings, architectureId, limit })}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <Play aria-hidden="true" className="size-4" />
            )}
            {busy ? t('experiments.starting') : t('experiments.start')}
          </button>
          {actionError !== null && <ActionError error={actionError} />}
        </section>

        <section aria-labelledby="current-heading" className="space-y-3">
          <h2 id="current-heading" className="text-lg font-semibold">
            {t('experiments.current')}
          </h2>
          {!showStatus ? (
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
                    onClick={() => void stop()}
                    className="ml-auto inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Square aria-hidden="true" className="size-4" />
                    {t('experiments.stop')}
                  </button>
                )}
              </div>
              <div>
                <progress
                  aria-label={t('experiments.progress.label')}
                  value={status.completed}
                  max={Math.max(status.total, 1)}
                  className="h-2 w-full"
                />
                <p className="mt-1 text-sm text-fg-muted">
                  {t('experiments.progress', {
                    completed: status.completed,
                    total: status.total,
                  })}{' '}
                  ({Math.round(batteryProgress(status) * 100)} %)
                </p>
              </div>
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
                      disabled={!live || active || busy}
                      onClick={() => void start({ kind: 'resume', experimentId: item.id })}
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
      </div>
    </>
  );
}
