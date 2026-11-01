import type { ModelOption } from './run';

export const PIPELINE_VERSIONS = ['2', '3', '3.1'] as const;
export type PipelineVersion = (typeof PIPELINE_VERSIONS)[number];

export const IMPROVEMENTS = [
  'reasoning_control',
  'answer_contract',
  'web_sources',
  'spreadsheet_tools',
  'multimedia_tools',
  'calculation_tools',
] as const;
export type Improvement = (typeof IMPROVEMENTS)[number];

export const CAPABILITIES = ['code', 'spreadsheet', 'document', 'multimedia', 'web'] as const;
export type Capability = (typeof CAPABILITIES)[number];

export const REASONING_MODES = ['off', 'bounded'] as const;
export type ReasoningMode = (typeof REASONING_MODES)[number];

export const SAMPLING_PROFILES = ['legacy', 'controlled', 'author'] as const;
export type SamplingProfile = (typeof SAMPLING_PROFILES)[number];

export const TOKEN_LIMIT = 8192;
export const SOLUTION_TOKENS_MIN = 128;
export const DEFAULT_SEED = 42;

/** How the agent is configured to run: what a battery or a single run uses. */
export interface ExperimentSettings {
  name: string;
  pipelineVersion: PipelineVersion;
  improvements: Improvement[];
  capabilities: Capability[];
  reasoningMode: ReasoningMode;
  thinkingTokens: number;
  solutionTokens: number;
  samplingProfile: SamplingProfile;
  seed: number | null;
  /** Null to use the server's default model. */
  model: ModelOption | null;
}

export type SettingsIssue =
  | 'name-empty'
  | 'tokens-range'
  | 'solution-min'
  | 'seed-range'
  | 'improvements-v2'
  | 'no-capabilities';

/** The V3.1 pipeline with all its improvements: the recommended starting point. */
export function defaultSettings(): ExperimentSettings {
  return {
    name: 'Studio',
    pipelineVersion: '3.1',
    improvements: [...IMPROVEMENTS],
    capabilities: [...CAPABILITIES],
    reasoningMode: 'bounded',
    thinkingTokens: 512,
    solutionTokens: 1024,
    samplingProfile: 'controlled',
    seed: DEFAULT_SEED,
    model: null,
  };
}

/** Switch version and move the dependent settings to what that version expects. */
export function setPipelineVersion(
  settings: ExperimentSettings,
  version: PipelineVersion,
): ExperimentSettings {
  const v31 = version === '3.1';
  return {
    ...settings,
    pipelineVersion: version,
    improvements: version === '2' ? [] : settings.improvements,
    samplingProfile: v31 ? 'controlled' : 'legacy',
    seed: v31 ? (settings.seed ?? DEFAULT_SEED) : null,
  };
}

/** What the backend would refuse, found before sending. */
export function settingsIssues(settings: ExperimentSettings): SettingsIssue[] {
  const issues: SettingsIssue[] = [];
  if (settings.name.trim() === '') issues.push('name-empty');
  const tokens = [settings.thinkingTokens, settings.solutionTokens];
  if (tokens.some((value) => !Number.isInteger(value) || value < 0 || value > TOKEN_LIMIT)) {
    issues.push('tokens-range');
  } else if (settings.solutionTokens < SOLUTION_TOKENS_MIN) {
    issues.push('solution-min');
  }
  if (
    settings.seed !== null &&
    (!Number.isInteger(settings.seed) || settings.seed < 0 || settings.seed >= 2 ** 32)
  ) {
    issues.push('seed-range');
  }
  if (settings.pipelineVersion === '2' && settings.improvements.length > 0) {
    issues.push('improvements-v2');
  }
  if (settings.capabilities.length === 0) issues.push('no-capabilities');
  return issues;
}

export interface WireExperiment {
  name: string;
  force_direct: boolean;
  enabled_capabilities: Capability[];
  pipeline_version: PipelineVersion;
  improvements: Improvement[];
  reasoning_mode: ReasoningMode;
  thinking_tokens: number;
  solution_tokens: number;
  sampling_profile: SamplingProfile;
  seed: number | null;
  architecture?: string;
  model?: { provider: ModelOption['provider']; model_id: string };
}

/** The `experiment` object the backend expects, with the architecture to run. */
export function toWireExperiment(
  settings: ExperimentSettings,
  architectureId: string | null,
): WireExperiment {
  return {
    name: settings.name.trim(),
    force_direct: false,
    enabled_capabilities: settings.capabilities,
    pipeline_version: settings.pipelineVersion,
    improvements: settings.improvements,
    reasoning_mode: settings.reasoningMode,
    thinking_tokens: settings.thinkingTokens,
    solution_tokens: settings.solutionTokens,
    sampling_profile: settings.samplingProfile,
    seed: settings.seed,
    ...(architectureId ? { architecture: architectureId } : {}),
    ...(settings.model
      ? { model: { provider: settings.model.provider, model_id: settings.model.modelId } }
      : {}),
  };
}
