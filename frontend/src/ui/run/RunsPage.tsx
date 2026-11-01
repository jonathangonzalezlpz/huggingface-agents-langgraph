import { Loader2, Play, X } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { loadLibrary } from '../../application/loadLibrary';
import type { Architecture } from '../../domain/types';
import type { GaiaQuestion, ModelOption } from '../../domain/run';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { useSystemStatus } from '../shell/SystemStatusProvider';
import { GaiaPicker } from './GaiaPicker';
import { RunResult } from './RunResult';
import { useRunner } from './useRunner';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';
const DEFAULT_MODEL = '__default__';

function versionLabel(t: ReturnType<typeof useI18n>['t'], architecture: Architecture): string {
  const name = architecture.architectureId;
  const version = architecture.version;
  if (version === null) return t('runs.architecture.builtin', { name });
  return architecture.validation.isValid
    ? t('runs.architecture.version', { name, version })
    : t('runs.architecture.invalid', { name, version });
}

function modelKey(option: ModelOption): string {
  return `${option.provider}:${option.modelId}`;
}

export function RunsPage() {
  const { t } = useI18n();
  const { architectures, models, runs, mode } = useServices();
  const status = useSystemStatus();
  const [params] = useSearchParams();
  const runner = useRunner(runs);

  const library = useAsyncData(useCallback(() => loadLibrary(architectures), [architectures]));
  const modelList = useAsyncData(useCallback(() => models.list(), [models]));

  const [selectedId, setSelectedId] = useState<string | null>(params.get('architecture'));
  const [question, setQuestion] = useState('');
  const [gaia, setGaia] = useState<GaiaQuestion | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [modelChoice, setModelChoice] = useState(DEFAULT_MODEL);

  const live = mode === 'live';
  const available = useMemo(() => (library.status === 'success' ? library.data : []), [library]);
  const selected = available.find((item) => item.id === selectedId) ?? null;
  const blocked = selected !== null && !selected.validation.isValid;
  const options = modelList.status === 'success' ? modelList.data : [];
  const examples = [t('runs.example.1'), t('runs.example.2'), t('runs.example.3')];
  const running = runner.state.status === 'running';
  const canRun = live && selected !== null && !blocked && question.trim() !== '' && !running;

  const grouped = useMemo(
    () => [...available].sort((a, b) => a.architectureId.localeCompare(b.architectureId)),
    [available],
  );

  const run = () => {
    if (!selected) return;
    const model = options.find((option) => modelKey(option) === modelChoice) ?? null;
    void runner.start({
      architectureId: selected.id,
      question: question.trim(),
      taskId: gaia?.taskId ?? `studio-${crypto.randomUUID()}`,
      fileName: gaia?.fileName ?? '',
      model,
    });
  };

  return (
    <>
      <PageHeader title={t('runs.title')} description={t('runs.description')} />

      {!live && (
        <p
          role="note"
          className="mb-4 rounded-lg border border-line-strong bg-info-soft p-3 text-sm"
        >
          {t('runs.demo')}
        </p>
      )}

      <section aria-labelledby="config-heading" className="max-w-3xl space-y-4">
        <h2 id="config-heading" className="text-lg font-semibold">
          {t('runs.config')}
        </h2>

        <div>
          <label htmlFor="run-architecture" className="mb-1 block text-sm font-medium">
            {t('runs.architecture')}
          </label>
          {library.status === 'error' ? (
            <ErrorNotice error={library.error} onRetry={library.reload} />
          ) : (
            <select
              id="run-architecture"
              className={FIELD}
              value={selectedId ?? ''}
              onChange={(event) => setSelectedId(event.target.value || null)}
            >
              <option value="">{t('runs.architecture.placeholder')}</option>
              {grouped.map((item) => (
                <option key={item.id} value={item.id}>
                  {versionLabel(t, item)}
                </option>
              ))}
            </select>
          )}
          {library.status === 'success' && available.length === 0 && (
            <p className="mt-1 text-sm text-fg-muted">{t('runs.architecture.none')}</p>
          )}
          {blocked && selected && (
            <p role="alert" className="mt-2 text-sm text-error">
              {t('runs.architecture.blocked')}{' '}
              <Link
                to={`/builder/architecture/${encodeURIComponent(selected.id)}`}
                className="underline underline-offset-2"
              >
                {t('runs.architecture.open')}
              </Link>
            </p>
          )}
        </div>

        <div>
          <label htmlFor="run-model" className="mb-1 block text-sm font-medium">
            {t('runs.model')}
          </label>
          <select
            id="run-model"
            className={FIELD}
            value={modelChoice}
            onChange={(event) => setModelChoice(event.target.value)}
          >
            <option value={DEFAULT_MODEL}>{t('runs.model.default')}</option>
            {options.map((option) => (
              <option key={modelKey(option)} value={modelKey(option)}>
                {option.modelId}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="run-question" className="mb-1 block text-sm font-medium">
            {t('runs.question')}
          </label>
          {gaia ? (
            <div className="flex items-start gap-2 rounded-lg border border-line-strong bg-muted p-3 text-sm">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-fg-muted">{t('runs.gaia.selected')}</p>
                <p>{gaia.question}</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setGaia(null);
                  setQuestion('');
                }}
                className="inline-flex items-center gap-1 text-sm underline underline-offset-2"
              >
                <X aria-hidden="true" className="size-4" />
                {t('runs.gaia.clear')}
              </button>
            </div>
          ) : (
            <textarea
              id="run-question"
              rows={3}
              value={question}
              placeholder={t('runs.question.placeholder')}
              onChange={(event) => setQuestion(event.target.value)}
              className={`${FIELD} py-2`}
            />
          )}
          {!gaia && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs text-fg-muted">{t('runs.examples')}</span>
              {examples.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuestion(example)}
                  className="rounded-full border border-line px-2.5 py-1 text-xs hover:bg-muted"
                >
                  {example}
                </button>
              ))}
              {live ? (
                <button
                  type="button"
                  onClick={() => setPickerOpen(true)}
                  className="rounded-full border border-line-strong px-2.5 py-1 text-xs font-medium hover:bg-muted"
                >
                  {t('runs.gaia.pick')}
                </button>
              ) : null}
            </div>
          )}
        </div>

        {status?.llm?.state === 'unavailable' && (
          <p role="note" className="text-sm text-warning">
            {t('runs.llm.warning')}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={!canRun}
            onClick={run}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <Play aria-hidden="true" className="size-4" />
            )}
            {running ? t('runs.running', { seconds: runner.elapsed }) : t('runs.run')}
          </button>
          {running && (
            <button
              type="button"
              onClick={runner.stopWaiting}
              className="min-h-10 rounded-lg border border-line-strong px-3 text-sm font-medium"
            >
              {t('runs.stopWaiting')}
            </button>
          )}
        </div>
        {running && <p className="text-sm text-fg-muted">{t('runs.running.hint')}</p>}
      </section>

      <GaiaPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={(item) => {
          setGaia(item);
          setQuestion(item.question);
        }}
      />

      <div className="mt-10">
        {runner.state.status === 'idle' && <p className="text-fg-muted">{t('runs.empty')}</p>}
        {runner.state.status === 'stopped' && (
          <p role="status" className="text-fg-muted">
            {t('runs.stopped')}
          </p>
        )}
        {runner.state.status === 'failed' && (
          <ErrorNotice error={runner.state.error} onRetry={run} />
        )}
        {runner.state.status === 'done' && <RunResult record={runner.state.record} />}
      </div>
    </>
  );
}
