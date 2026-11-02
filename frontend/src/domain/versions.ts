import type { ArchitectureSummary } from './types';

export type VersionEntry<T extends ArchitectureSummary = ArchitectureSummary> = T & {
  /** The version just before this one in the same architecture, if any. */
  previous: T | null;
};

export interface ArchitectureGroup<T extends ArchitectureSummary = ArchitectureSummary> {
  architectureId: string;
  versions: VersionEntry<T>[];
  latest: T;
}

const byVersionDescending = (a: ArchitectureSummary, b: ArchitectureSummary) =>
  (b.version ?? 0) - (a.version ?? 0);

/** Versions grouped by architecture: the built-in first, then alphabetical; newest first. */
export function groupVersions<T extends ArchitectureSummary>(
  summaries: readonly T[],
): ArchitectureGroup<T>[] {
  const byName = new Map<string, T[]>();
  for (const summary of summaries) {
    byName.set(summary.architectureId, [...(byName.get(summary.architectureId) ?? []), summary]);
  }
  return [...byName.entries()]
    .map(([architectureId, items]) => {
      const sorted = [...items].sort(byVersionDescending);
      const versions = sorted.map((item, index) => ({
        ...item,
        previous: sorted[index + 1] ?? null,
      }));
      return { architectureId, versions, latest: sorted[0] as T };
    })
    .sort((a, b) => {
      if (a.latest.readOnly !== b.latest.readOnly) return a.latest.readOnly ? -1 : 1;
      return a.architectureId.localeCompare(b.architectureId);
    });
}
