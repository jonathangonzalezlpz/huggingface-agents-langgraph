import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { defaultSettings, settingsIssues } from '../../domain/experiment';
import type { GaiaQuestion } from '../../domain/run';
import { useI18n } from '../../i18n/I18nProvider';
import { PageHeader } from '../components/PageHeader';
import { useLibrary } from '../hooks/useLibrary';
import { useModelCatalog } from '../hooks/useModelCatalog';
import { useServices } from '../services';
import { useSystemStatus } from '../shell/SystemStatusProvider';
import { ArchitecturePicker } from './ArchitecturePicker';
import { QuestionField } from './QuestionField';
import { RunControls } from './RunControls';
import { RunOutcome } from './RunOutcome';
import { SettingsPanel } from './SettingsPanel';
import { useRunner } from './useRunner';

/** Run one question through a stored architecture and look at the path it took. */
export function RunsPage() {
  const { t } = useI18n();
  const { runs, mode } = useServices();
  const status = useSystemStatus();
  const [params] = useSearchParams();
  const runner = useRunner(runs);
  const library = useLibrary();
  const { models, visionModels } = useModelCatalog();

  const [architectureId, setArchitectureId] = useState<string | null>(params.get('architecture'));
  const [question, setQuestion] = useState('');
  const [gaia, setGaia] = useState<GaiaQuestion | null>(null);
  const [settings, setSettings] = useState(defaultSettings);

  const live = mode === 'live';
  const running = runner.state.status === 'running';
  const selected =
    library.status === 'success'
      ? (library.data.find((item) => item.id === architectureId) ?? null)
      : null;
  const canRun =
    live &&
    selected !== null &&
    selected.validation.isValid &&
    question.trim() !== '' &&
    !running &&
    settingsIssues(settings).length === 0;

  const run = () => {
    if (!selected) return;
    void runner.start({
      architectureId: selected.id,
      question: question.trim(),
      taskId: gaia?.taskId ?? `studio-${crypto.randomUUID()}`,
      fileName: gaia?.fileName ?? '',
      settings,
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
        <ArchitecturePicker
          id="run-architecture"
          library={library}
          value={architectureId}
          onChange={setArchitectureId}
        />
        <SettingsPanel
          settings={settings}
          models={models}
          visionModels={visionModels}
          disabled={running}
          onChange={setSettings}
        />
        <QuestionField
          text={question}
          onTextChange={setQuestion}
          gaia={gaia}
          onGaiaChange={setGaia}
          gaiaAvailable={live}
        />
        {status?.llm?.state === 'unavailable' && (
          <p role="note" className="text-sm text-warning">
            {t('runs.llm.warning')}
          </p>
        )}
        <RunControls
          canRun={canRun}
          running={running}
          elapsed={runner.elapsed}
          onRun={run}
          onStopWaiting={runner.stopWaiting}
        />
      </section>

      <div className="mt-10">
        <RunOutcome state={runner.state} onRetry={run} />
      </div>
    </>
  );
}
