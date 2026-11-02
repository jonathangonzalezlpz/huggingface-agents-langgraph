import { CheckCircle2, ExternalLink, Pause, Play, RotateCcw, XCircle } from 'lucide-react';
import { useCallback, useEffect, useId, useMemo, useState } from 'react';

import { documentFromArchitecture } from '../../domain/editor/templates';
import type { RunRecord } from '../../domain/run';
import { failedStep } from '../../domain/runPath';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { StatusBadge } from '../components/StatusBadge';
import { useAsyncData } from '../hooks/useAsyncData';
import { computeLayout } from '../editor/autoLayout';
import { useServices } from '../services';
import { RunCanvas } from './RunCanvas';

const REPLAY_INTERVAL_MS = 700;
const CONTROL =
  'inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-2.5 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50';

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-fg-muted">{label}</dt>
      <dd className="mt-0.5 text-sm">{children}</dd>
    </div>
  );
}

function RunPath({ record }: { record: RunRecord }) {
  const { t } = useI18n();
  const { architectures, catalog, layouts } = useServices();
  const architectureId = record.architecture?.id ?? null;

  const load = useCallback(async () => {
    if (!architectureId) return null;
    const [architecture, components, stored] = await Promise.all([
      architectures.get(architectureId),
      catalog.getCatalog(),
      layouts.get(architectureId).catch(() => ({})),
    ]);
    const base = documentFromArchitecture(
      architecture,
      components,
      architecture.architectureId,
      stored,
    );
    const placed = base.graph.nodes.every((node) => base.layout[node.id]);
    const document = placed
      ? base
      : { ...base, layout: { ...computeLayout(base.graph), ...base.layout } };
    return { document, components };
  }, [architectureId, architectures, catalog, layouts]);
  const state = useAsyncData(load);

  const total = record.steps.length;
  const [position, setPosition] = useState(total);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const sliderId = useId();
  const completed = record.status === 'completed';

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setPosition((current) => {
        if (current >= total) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, REPLAY_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [playing, total]);

  const view = useMemo(
    () => ({ steps: record.steps, position, completed }),
    [record.steps, position, completed],
  );

  const restart = () => {
    setPosition(0);
    setPlaying(true);
  };
  const togglePlay = () => {
    if (!playing && position >= total) setPosition(0);
    setPlaying((current) => !current);
  };
  const detail = selected !== null ? record.steps[selected] : null;

  return (
    <section aria-labelledby="path-heading" className="space-y-3">
      <h3 id="path-heading" className="text-sm font-semibold">
        {t('runs.path')}
      </h3>

      <div className="h-[26rem] overflow-hidden rounded-xl border border-line bg-surface">
        {state.status === 'loading' && <p className="p-4 text-fg-muted">{t('common.loading')}</p>}
        {state.status === 'error' && (
          <div className="p-4">
            <ErrorNotice error={state.error} onRetry={state.reload} />
          </div>
        )}
        {state.status === 'success' && state.data === null && (
          <p className="p-4 text-sm text-fg-muted">{t('runs.noStepsArchitecture')}</p>
        )}
        {state.status === 'success' && state.data && (
          <RunCanvas document={state.data.document} catalog={state.data.components} view={view} />
        )}
      </div>
      <p className="text-xs text-fg-muted">{t('runs.legend')}</p>

      {total > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={togglePlay} className={CONTROL}>
            {playing ? (
              <Pause aria-hidden="true" className="size-4" />
            ) : (
              <Play aria-hidden="true" className="size-4" />
            )}
            {playing ? t('runs.replay.pause') : t('runs.replay.play')}
          </button>
          <button type="button" onClick={restart} className={CONTROL}>
            <RotateCcw aria-hidden="true" className="size-4" />
            {t('runs.replay.restart')}
          </button>
          <label htmlFor={sliderId} className="sr-only">
            {t('runs.replay.slider')}
          </label>
          <input
            id={sliderId}
            type="range"
            min={0}
            max={total}
            value={position}
            onChange={(event) => {
              setPlaying(false);
              setPosition(Number(event.target.value));
            }}
            className="min-w-40 flex-1"
          />
          <span className="text-sm text-fg-muted" aria-live="polite">
            {t('runs.replay.step', { current: position, total })}
          </span>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <section aria-labelledby="timeline-heading">
          <h3 id="timeline-heading" className="mb-2 text-sm font-semibold">
            {t('runs.timeline')}
          </h3>
          <ol className="space-y-1.5">
            {record.steps.map((step, index) => (
              <li key={`${step.node}-${index}`}>
                <button
                  type="button"
                  aria-current={selected === index ? 'step' : undefined}
                  onClick={() => {
                    setPlaying(false);
                    setSelected(index);
                    setPosition(index + 1);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-sm ${
                    selected === index ? 'border-accent bg-accent-soft' : 'border-line bg-surface'
                  } ${index >= position ? 'opacity-50' : ''}`}
                >
                  <span className="w-5 text-xs text-fg-muted">{index + 1}</span>
                  {step.error ? (
                    <XCircle aria-hidden="true" className="size-4 shrink-0 text-error" />
                  ) : (
                    <CheckCircle2 aria-hidden="true" className="size-4 shrink-0 text-success" />
                  )}
                  <span className="min-w-0 flex-1 truncate font-mono">{step.node}</span>
                  <span className="text-xs text-fg-muted">{step.durationSeconds.toFixed(1)} s</span>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="detail-heading">
          <h3 id="detail-heading" className="mb-2 text-sm font-semibold">
            {t('runs.step.detail')}
          </h3>
          {detail ? (
            <dl className="space-y-2 rounded-lg border border-line bg-surface p-3 text-sm">
              <Meta label={t('editor.node.id')}>
                <span className="font-mono">{detail.node}</span>
              </Meta>
              <Meta label={t('runs.meta.duration')}>{detail.durationSeconds.toFixed(2)} s</Meta>
              <Meta label={t('runs.step.wrote')}>
                {detail.updatedFields.length === 0 ? (
                  <span className="text-fg-muted">{t('runs.step.nothing')}</span>
                ) : (
                  <span className="flex flex-wrap gap-1">
                    {detail.updatedFields.map((field) => (
                      <code
                        key={field}
                        className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs"
                      >
                        {field}
                      </code>
                    ))}
                  </span>
                )}
              </Meta>
              {detail.error && (
                <Meta label={t('runs.step.error')}>
                  <span className="text-error">{detail.error}</span>
                </Meta>
              )}
            </dl>
          ) : (
            <p className="text-sm text-fg-muted">{t('runs.step.pick')}</p>
          )}
        </section>
      </div>
    </section>
  );
}

/** The outcome of a run: answer, figures, the path it took, and where it failed if it did. */
export function RunResult({ record }: { record: RunRecord }) {
  const { t, tp } = useI18n();
  const failed = failedStep(record.steps);
  const completed = record.status === 'completed';
  const architecture = record.architecture;

  return (
    <section aria-labelledby="result-heading" className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="result-heading" className="text-lg font-semibold">
          {t('runs.result')}
        </h2>
        <StatusBadge tone={completed ? 'success' : 'error'}>
          {t(completed ? 'runs.status.completed' : 'runs.status.error')}
        </StatusBadge>
        <a
          href={`/api/runs/${encodeURIComponent(record.id)}`}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent-fg underline underline-offset-2"
        >
          <ExternalLink aria-hidden="true" className="size-4" />
          {t('runs.trace')}
        </a>
      </div>

      {!completed && (
        <div
          role="alert"
          className="rounded-xl border border-line-strong bg-error-soft p-4 text-error"
        >
          <p className="font-semibold">{t('runs.error.title')}</p>
          {failed && <p className="text-sm">{t('runs.failedAt', { node: failed.node })}</p>}
          {record.error && <p className="mt-1 text-sm">{record.error}</p>}
        </div>
      )}

      <div className="rounded-xl border border-line bg-surface p-4">
        <p className="text-xs font-medium text-fg-muted">{t('runs.answer')}</p>
        <p className="mt-1 text-lg font-semibold">
          {record.answer ?? <span className="text-fg-muted">{t('runs.noAnswer')}</span>}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Meta label={t('runs.meta.duration')}>{record.durationSeconds.toFixed(1)} s</Meta>
        <Meta label={t('runs.meta.route')}>{record.route ?? '—'}</Meta>
        <Meta label={t('runs.meta.steps')}>{tp('runs.visits', record.steps.length)}</Meta>
        <Meta label={t('runs.meta.architecture')}>
          <span className="font-mono">
            {architecture?.id === null || architecture === null
              ? '—'
              : architecture.version === null
                ? architecture.id
                : `${architecture.id} (v${architecture.version})`}
          </span>
        </Meta>
        <Meta label={t('runs.meta.model')}>
          <span className="font-mono">{record.modelId ?? t('runs.model.default')}</span>
        </Meta>
      </dl>

      <RunPath record={record} />
    </section>
  );
}
