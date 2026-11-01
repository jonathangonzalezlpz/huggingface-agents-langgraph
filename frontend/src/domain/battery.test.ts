import { describe, expect, it } from 'vitest';

import {
  IDLE_BATTERY,
  batteryProgress,
  canResume,
  isBatteryActive,
  type ExperimentSummary,
} from './battery';

const summary = (over: Partial<ExperimentSummary> = {}): ExperimentSummary => ({
  id: 'a',
  status: 'cancelled',
  name: 'x',
  pipelineVersion: '3.1',
  architecture: null,
  completed: 5,
  total: 20,
  createdAt: null,
  averageSeconds: null,
  score: null,
  ...over,
});

describe('battery status', () => {
  it('is active only while running or stopping', () => {
    expect(isBatteryActive({ ...IDLE_BATTERY, state: 'running' })).toBe(true);
    expect(isBatteryActive({ ...IDLE_BATTERY, state: 'stopping' })).toBe(true);
    for (const state of ['idle', 'completed', 'cancelled', 'failed'] as const) {
      expect(isBatteryActive({ ...IDLE_BATTERY, state })).toBe(false);
    }
  });

  it('measures progress without dividing by zero', () => {
    expect(batteryProgress(IDLE_BATTERY)).toBe(0);
    expect(batteryProgress({ ...IDLE_BATTERY, completed: 5, total: 20 })).toBe(0.25);
    expect(batteryProgress({ ...IDLE_BATTERY, completed: 25, total: 20 })).toBe(1);
  });
});

describe('resuming', () => {
  it('is offered for unfinished experiments only', () => {
    expect(canResume(summary())).toBe(true);
    expect(canResume(summary({ status: 'completed', completed: 20 }))).toBe(false);
    expect(canResume(summary({ status: 'cancelled', completed: 20 }))).toBe(false);
  });
});
