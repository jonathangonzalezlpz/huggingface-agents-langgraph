import { Loader2, Play } from 'lucide-react';
import { useState } from 'react';

import type { BatteryRequest } from '../../domain/battery';
import { StudioError } from '../../domain/errors';
import { defaultSettings, settingsIssues } from '../../domain/experiment';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useLibrary } from '../hooks/useLibrary';
import { useModelCatalog } from '../hooks/useModelCatalog';
import { ArchitecturePicker } from '../run/ArchitecturePicker';
import { SettingsPanel } from '../run/SettingsPanel';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';
export const MAX_QUESTIONS = 20;

/** Why starting failed, in words the user can act on; unknown failures get the generic notice. */
function StartError({ error }: { error: unknown }) {
  const { t } = useI18n();
  if (error instanceof StudioError && error.kind === 'http') {
    if (error.status === 409) return <p role="alert">{t('experiments.error.busy')}</p>;
    if (error.status === 503) return <p role="alert">{t('experiments.error.unavailable')}</p>;
    if (error.status === 400) return <p role="alert">{t('experiments.error.rejected')}</p>;
  }
  return <ErrorNotice error={error} />;
}

function QuestionLimit({
  value,
  disabled,
  onChange,
}: {
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  const { t } = useI18n();
  return (
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
        value={Number.isNaN(value) ? '' : value}
        disabled={disabled}
        onChange={(event) =>
          onChange(event.target.value.trim() === '' ? Number.NaN : Number(event.target.value))
        }
      />
      <p className="mt-1 text-xs text-fg-muted">{t('experiments.limit.hint')}</p>
    </div>
  );
}

/** Choose what to run and start a battery of GAIA questions on the server. */
export function BatteryForm({
  live,
  loaded,
  active,
  busy,
  error,
  onStart,
}: {
  live: boolean;
  loaded: boolean;
  active: boolean;
  busy: boolean;
  error: unknown;
  onStart: (request: BatteryRequest) => void;
}) {
  const { t } = useI18n();
  const library = useLibrary();
  const { models, visionModels } = useModelCatalog();
  const [settings, setSettings] = useState(defaultSettings);
  const [architectureId, setArchitectureId] = useState<string | null>(null);
  const [limit, setLimit] = useState(MAX_QUESTIONS);

  const limitValid = Number.isInteger(limit) && limit >= 1 && limit <= MAX_QUESTIONS;
  const canStart =
    live &&
    loaded &&
    !active &&
    !busy &&
    architectureId !== null &&
    limitValid &&
    settingsIssues(settings).length === 0;

  return (
    <section aria-labelledby="battery-heading" className="space-y-4">
      <div>
        <h2 id="battery-heading" className="text-lg font-semibold">
          {t('experiments.battery')}
        </h2>
        <p className="text-sm text-fg-muted">{t('experiments.battery.hint')}</p>
        <p className="text-sm text-fg-muted">{t('experiments.battery.cost')}</p>
      </div>
      <ArchitecturePicker
        id="battery-architecture"
        library={library}
        value={architectureId}
        onChange={setArchitectureId}
        disabled={active}
        runnableOnly
      />
      <SettingsPanel
        settings={settings}
        models={models}
        visionModels={visionModels}
        disabled={active}
        onChange={setSettings}
      />
      <QuestionLimit value={limit} disabled={active} onChange={setLimit} />
      <button
        type="button"
        disabled={!canStart}
        onClick={() => architectureId && onStart({ kind: 'new', settings, architectureId, limit })}
        className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? (
          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
        ) : (
          <Play aria-hidden="true" className="size-4" />
        )}
        {busy ? t('experiments.starting') : t('experiments.start')}
      </button>
      {error !== null && <StartError error={error} />}
    </section>
  );
}
