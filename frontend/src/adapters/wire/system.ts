/** Wire format of the backend's status and its translation into the domain model. */
import { z } from 'zod';

import type { LlmState, SystemStatus } from '../../domain/types';
import type { Wire } from './shared';

export const statusSchema = z.object({
  llm: z.object({ state: z.string(), name: z.string() }).optional(),
  gpu: z
    .object({
      available: z.boolean(),
      name: z.string().nullish(),
      backend: z.string().nullish(),
    })
    .optional(),
  host_memory: z.object({ available_mib: z.number(), total_mib: z.number() }).optional(),
});

const LLM_STATES: readonly LlmState[] = ['ready', 'sleeping', 'loading', 'unavailable'];

export function toStatus(wire: Wire<typeof statusSchema>): SystemStatus {
  const reported = wire.llm?.state;
  return {
    backend: 'online',
    llm: wire.llm
      ? {
          state: LLM_STATES.find((known) => known === reported) ?? 'unavailable',
          name: wire.llm.name,
        }
      : null,
    gpu: wire.gpu
      ? {
          available: wire.gpu.available,
          name: wire.gpu.name ?? null,
          backend: wire.gpu.backend ?? null,
        }
      : null,
    hostMemory: wire.host_memory
      ? { availableMib: wire.host_memory.available_mib, totalMib: wire.host_memory.total_mib }
      : null,
  };
}
