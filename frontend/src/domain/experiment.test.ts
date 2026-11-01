import { describe, expect, it } from 'vitest';

import {
  CAPABILITIES,
  IMPROVEMENTS,
  defaultSettings,
  setPipelineVersion,
  settingsIssues,
  toWireExperiment,
} from './experiment';

describe('default settings', () => {
  it('are the V3.1 pipeline with every improvement and capability', () => {
    const settings = defaultSettings();
    expect(settings.pipelineVersion).toBe('3.1');
    expect(settings.improvements).toEqual([...IMPROVEMENTS]);
    expect(settings.capabilities).toEqual([...CAPABILITIES]);
    expect(settings.samplingProfile).toBe('controlled');
    expect(settings.seed).toBe(42);
    expect(settings.model).toBeNull();
    expect(settingsIssues(settings)).toEqual([]);
  });
});

describe('changing the pipeline version', () => {
  it('V2 has no improvements, legacy sampling and no seed', () => {
    const v2 = setPipelineVersion(defaultSettings(), '2');
    expect(v2).toMatchObject({
      pipelineVersion: '2',
      improvements: [],
      samplingProfile: 'legacy',
      seed: null,
    });
    expect(settingsIssues(v2)).toEqual([]);
  });

  it('going back to V3.1 restores controlled sampling and a seed', () => {
    const back = setPipelineVersion(setPipelineVersion(defaultSettings(), '2'), '3.1');
    expect(back).toMatchObject({ samplingProfile: 'controlled', seed: 42, improvements: [] });
  });

  it('V3 keeps its improvements and uses legacy sampling', () => {
    const v3 = setPipelineVersion(defaultSettings(), '3');
    expect(v3.improvements).toHaveLength(IMPROVEMENTS.length);
    expect(v3.samplingProfile).toBe('legacy');
    expect(v3.seed).toBeNull();
  });
});

describe('validation', () => {
  it.each([
    [{ thinkingTokens: -1 }, 'tokens-range'],
    [{ solutionTokens: 9000 }, 'tokens-range'],
    [{ solutionTokens: 100 }, 'solution-min'],
    [{ seed: 2 ** 32 }, 'seed-range'],
    [{ seed: 1.5 }, 'seed-range'],
    [{ name: '   ' }, 'name-empty'],
    [{ capabilities: [] }, 'no-capabilities'],
  ])('reports %j as %s', (change, code) => {
    expect(settingsIssues({ ...defaultSettings(), ...change })).toContain(code);
  });

  it('rejects improvements on V2', () => {
    const settings = {
      ...setPipelineVersion(defaultSettings(), '2'),
      improvements: ['answer_contract' as const],
    };
    expect(settingsIssues(settings)).toContain('improvements-v2');
  });
});

describe('wire form', () => {
  it('uses the backend field names and omits an unset model', () => {
    const wire = toWireExperiment(defaultSettings(), 'abc');
    expect(wire).toMatchObject({
      name: 'Studio',
      pipeline_version: '3.1',
      reasoning_mode: 'bounded',
      thinking_tokens: 512,
      solution_tokens: 1024,
      sampling_profile: 'controlled',
      seed: 42,
      architecture: 'abc',
      force_direct: false,
    });
    expect(wire).not.toHaveProperty('model');
    expect(wire.enabled_capabilities).toEqual([...CAPABILITIES]);
  });

  it('sends the chosen model', () => {
    const wire = toWireExperiment(
      { ...defaultSettings(), model: { provider: 'ollama', modelId: 'llama3' } },
      'abc',
    );
    expect(wire.model).toEqual({ provider: 'ollama', model_id: 'llama3' });
  });

  it('leaves the architecture out when none is given', () => {
    expect(toWireExperiment(defaultSettings(), null)).not.toHaveProperty('architecture');
  });
});

describe('wire form keeps the chosen capabilities, models and improvements', () => {
  // Replaces the Python check that read these values back out of the old interface.
  it.each(['2', '3', '3.1'] as const)('for pipeline version %s', (version) => {
    const settings = setPipelineVersion(
      {
        ...defaultSettings(),
        name: 'Custom',
        capabilities: ['web'],
        improvements: ['reasoning_control'],
        model: { provider: 'configured', modelId: 'reasoner' },
        visionModel: { provider: 'configured', modelId: 'vision' },
      },
      version,
    );
    const wire = toWireExperiment(settings, null);
    expect(wire.enabled_capabilities).toEqual(['web']);
    expect(wire.model?.model_id).toBe('reasoner');
    expect(wire.vision_model?.model_id).toBe('vision');
    expect(wire.improvements).toEqual(version === '2' ? [] : ['reasoning_control']);
    expect(wire.seed).toBe(version === '3.1' ? 42 : null);
  });

  it('leaves the vision model out when the original one is used', () => {
    expect(toWireExperiment(defaultSettings(), null)).not.toHaveProperty('vision_model');
  });
});
