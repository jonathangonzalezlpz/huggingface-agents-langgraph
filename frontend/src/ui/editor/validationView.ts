import type { Diagnostic } from '../../domain/types';
import type { AvailabilityView } from './InspectorFields';
import type { Validated } from './useValidation';

/** The findings to draw on the canvas: none while the graph has changed since the check. */
export function visibleDiagnostics(validated: Validated, stale: boolean): Diagnostic[] {
  return validated.view.status === 'done' && !stale ? validated.view.report.diagnostics : [];
}

/** What the inspector can say about the data available at the selected node. */
export function availabilityView(
  validated: Validated,
  stale: boolean,
  selectedId: string | null,
): AvailabilityView {
  const { view } = validated;
  if (view.status === 'unavailable') return { status: 'unavailable' };
  if (view.status !== 'done') return { status: 'pending' };
  if (stale) return { status: 'stale' };
  return {
    status: 'ready',
    node: selectedId ? (view.report.availability[selectedId] ?? null) : null,
  };
}

/** The graph was checked, has not changed since, and has errors. */
export function hasErrorsNow(validated: Validated, stale: boolean): boolean {
  return validated.view.status === 'done' && !stale && !validated.view.report.isValid;
}
