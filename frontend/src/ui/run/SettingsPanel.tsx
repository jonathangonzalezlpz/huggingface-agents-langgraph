import { useId } from 'react';

import {
  CAPABILITIES,
  IMPROVEMENTS,
  PIPELINE_VERSIONS,
  REASONING_MODES,
  SAMPLING_PROFILES,
  defaultSettings,
  setPipelineVersion,
  settingsIssues,
  type Capability,
  type ExperimentSettings,
  type Improvement,
  type PipelineVersion,
} from '../../domain/experiment';
import type { ModelOption } from '../../domain/run';
import { useI18n } from '../../i18n/I18nProvider';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';
const DEFAULT_MODEL = '__default__';

const modelKey = (option: ModelOption) => `${option.provider}:${option.modelId}`;

function toggle<T>(items: readonly T[], item: T, order: readonly T[]): T[] {
  return order.filter((candidate) =>
    candidate === item ? !items.includes(item) : items.includes(candidate),
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string | undefined;
  children: (id: string) => React.ReactNode;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {children(id)}
      {hint && <p className="mt-1 text-xs text-fg-muted">{hint}</p>}
    </div>
  );
}

function CheckGroup<T extends string>({
  legend,
  options,
  selected,
  disabled,
  label,
  onToggle,
}: {
  legend: string;
  options: readonly T[];
  selected: readonly T[];
  disabled?: boolean;
  label: (option: T) => string;
  onToggle: (option: T) => void;
}) {
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-1 text-sm font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {options.map((option) => (
          <label key={option} className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => onToggle(option)}
            />
            {label(option)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Everything that decides how the agent runs: the common choices first, the rest folded away. */
export function SettingsPanel({
  settings,
  models,
  visionModels,
  disabled = false,
  onChange,
}: {
  settings: ExperimentSettings;
  models: readonly ModelOption[];
  visionModels: readonly ModelOption[];
  disabled?: boolean;
  onChange: (next: ExperimentSettings) => void;
}) {
  const { t } = useI18n();
  const issues = settingsIssues(settings);
  const v2 = settings.pipelineVersion === '2';
  const v31 = settings.pipelineVersion === '3.1';
  const patch = (change: Partial<ExperimentSettings>) => onChange({ ...settings, ...change });
  const number = (value: string) => (value.trim() === '' ? Number.NaN : Number(value));

  return (
    <fieldset disabled={disabled} className="space-y-4">
      <legend className="sr-only">{t('settings.title')}</legend>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('settings.version')}>
          {(id) => (
            <select
              id={id}
              className={FIELD}
              value={settings.pipelineVersion}
              onChange={(event) =>
                onChange(setPipelineVersion(settings, event.target.value as PipelineVersion))
              }
            >
              {PIPELINE_VERSIONS.map((version) => (
                <option key={version} value={version}>
                  {t(`settings.version.${version}`)}
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field
          label={t('runs.model')}
          hint={models.length === 0 ? t('settings.model.none') : t('settings.model.hint')}
        >
          {(id) => (
            <select
              id={id}
              className={FIELD}
              value={settings.model ? modelKey(settings.model) : DEFAULT_MODEL}
              onChange={(event) =>
                patch({
                  model: models.find((option) => modelKey(option) === event.target.value) ?? null,
                })
              }
            >
              <option value={DEFAULT_MODEL}>{t('runs.model.default')}</option>
              {models.map((option) => (
                <option key={modelKey(option)} value={modelKey(option)}>
                  {option.modelId}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>

      {v2 ? (
        <p className="text-sm text-fg-muted">{t('settings.improvements.none')}</p>
      ) : (
        <CheckGroup<Improvement>
          legend={t('settings.improvements')}
          options={IMPROVEMENTS}
          selected={settings.improvements}
          label={(option) => t(`settings.improvement.${option}`)}
          onToggle={(option) =>
            patch({ improvements: toggle(settings.improvements, option, IMPROVEMENTS) })
          }
        />
      )}

      {v31 && (
        <Field label={t('settings.seed')} hint={t('settings.seed.hint')}>
          {(id) => (
            <input
              id={id}
              type="number"
              className={`${FIELD} max-w-48`}
              value={Number.isNaN(settings.seed) ? '' : (settings.seed ?? '')}
              onChange={(event) => patch({ seed: number(event.target.value) })}
            />
          )}
        </Field>
      )}

      <details className="rounded-lg border border-line p-3">
        <summary className="cursor-pointer text-sm font-medium">{t('settings.advanced')}</summary>
        <div className="mt-3 space-y-4">
          <Field label={t('settings.name')}>
            {(id) => (
              <input
                id={id}
                className={FIELD}
                value={settings.name}
                onChange={(event) => patch({ name: event.target.value })}
              />
            )}
          </Field>

          <Field
            label={t('settings.vision')}
            hint={visionModels.length === 0 ? t('settings.vision.none') : undefined}
          >
            {(id) => (
              <select
                id={id}
                className={FIELD}
                value={settings.visionModel ? modelKey(settings.visionModel) : DEFAULT_MODEL}
                onChange={(event) =>
                  patch({
                    visionModel:
                      visionModels.find((option) => modelKey(option) === event.target.value) ??
                      null,
                  })
                }
              >
                <option value={DEFAULT_MODEL}>{t('settings.vision.default')}</option>
                {visionModels.map((option) => (
                  <option key={modelKey(option)} value={modelKey(option)}>
                    {option.modelId}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <CheckGroup<Capability>
            legend={t('settings.capabilities')}
            options={CAPABILITIES}
            selected={settings.capabilities}
            label={(option) => t(`settings.capability.${option}`)}
            onToggle={(option) =>
              patch({ capabilities: toggle(settings.capabilities, option, CAPABILITIES) })
            }
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('settings.reasoning')}>
              {(id) => (
                <select
                  id={id}
                  className={FIELD}
                  value={settings.reasoningMode}
                  onChange={(event) =>
                    patch({
                      reasoningMode: event.target.value as ExperimentSettings['reasoningMode'],
                    })
                  }
                >
                  {REASONING_MODES.map((mode) => (
                    <option key={mode} value={mode}>
                      {t(`settings.reasoning.${mode}`)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={t('settings.sampling')}>
              {(id) => (
                <select
                  id={id}
                  className={FIELD}
                  value={settings.samplingProfile}
                  onChange={(event) =>
                    patch({
                      samplingProfile: event.target.value as ExperimentSettings['samplingProfile'],
                    })
                  }
                >
                  {SAMPLING_PROFILES.map((profile) => (
                    <option key={profile} value={profile}>
                      {t(`settings.sampling.${profile}`)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={t('settings.thinking')}>
              {(id) => (
                <input
                  id={id}
                  type="number"
                  className={FIELD}
                  value={Number.isNaN(settings.thinkingTokens) ? '' : settings.thinkingTokens}
                  onChange={(event) => patch({ thinkingTokens: number(event.target.value) })}
                />
              )}
            </Field>
            <Field label={t('settings.solution')}>
              {(id) => (
                <input
                  id={id}
                  type="number"
                  className={FIELD}
                  value={Number.isNaN(settings.solutionTokens) ? '' : settings.solutionTokens}
                  onChange={(event) => patch({ solutionTokens: number(event.target.value) })}
                />
              )}
            </Field>
          </div>
        </div>
      </details>

      {issues.length > 0 && (
        <ul role="alert" className="space-y-0.5 text-sm text-error">
          {issues.map((issue) => (
            <li key={issue}>{t(`settings.issue.${issue}`)}</li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() =>
          onChange({
            ...defaultSettings(),
            model: settings.model,
            visionModel: settings.visionModel,
          })
        }
        className="text-sm underline underline-offset-2"
      >
        {t('settings.reset')}
      </button>
    </fieldset>
  );
}
