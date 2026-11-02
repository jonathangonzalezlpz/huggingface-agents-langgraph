import type { Architecture } from '../domain/types';
import type { ArchitecturePort } from '../ports';

/** Every stored architecture with its definition and current validation. */
export async function loadLibrary(architectures: ArchitecturePort): Promise<Architecture[]> {
  const summaries = await architectures.list();
  return Promise.all(summaries.map((summary) => architectures.get(summary.id)));
}
