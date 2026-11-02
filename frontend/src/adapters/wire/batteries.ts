/** Wire format of the backend's background batteries and its translation into the domain model. */
import { z } from 'zod';

import type { BatteryStatus } from '../../domain/battery';

const BATTERY_STATES = ['idle', 'running', 'stopping', 'completed', 'cancelled', 'failed'] as const;

export const batterySchema = z.object({
  state: z.string(),
  experiment_id: z.string().nullish(),
  name: z.string().nullish(),
  completed: z.number().default(0),
  total: z.number().default(0),
  error: z.string().nullish(),
  started_at: z.string().nullish(),
});

export function toBatteryStatus(wire: z.output<typeof batterySchema>): BatteryStatus {
  const state = BATTERY_STATES.find((candidate) => candidate === wire.state);
  return {
    state: state ?? 'failed',
    experimentId: wire.experiment_id ?? null,
    name: wire.name ?? null,
    completed: wire.completed,
    total: wire.total,
    error: state ? (wire.error ?? null) : `Unknown battery state: ${wire.state}`,
    startedAt: wire.started_at ?? null,
  };
}
