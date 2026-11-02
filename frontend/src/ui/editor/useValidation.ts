import { useEffect, useRef, useState } from 'react';

import { toDefinition } from '../../domain/editor/convert';
import type { EditorGraph } from '../../domain/editor/model';
import { StudioError } from '../../domain/errors';
import type { ValidationReport } from '../../domain/types';
import { useServices } from '../services';
import type { ValidationView } from './DiagnosticsPanel';

const VALIDATION_DELAY_MS = 600;

/** The latest validation result and the graph it was computed for. */
export interface Validated {
  view: ValidationView;
  graph: EditorGraph | null;
}

/**
 * Validate the graph shortly after every change, keeping only the answer to the newest request.
 * When the backend cannot validate (demo mode) the automatic checks stop, and a manual one is
 * still possible.
 */
export function useValidation({
  graph,
  initialGraph,
  readOnly,
  initialValidation,
}: {
  graph: EditorGraph;
  initialGraph: EditorGraph;
  readOnly: boolean;
  initialValidation?: ValidationReport | undefined;
}) {
  const { validation } = useServices();
  const [validated, setValidated] = useState<Validated>(
    initialValidation
      ? { view: { status: 'done', report: initialValidation }, graph: initialGraph }
      : { view: { status: 'idle' }, graph: null },
  );
  const [validating, setValidating] = useState(false);
  const [automatic, setAutomatic] = useState(true);
  const requestSerial = useRef(0);

  const validate = async (target: EditorGraph) => {
    const serial = ++requestSerial.current;
    setValidating(true);
    try {
      const report = await validation.validate(toDefinition(target));
      if (serial !== requestSerial.current) return;
      setValidated({ view: { status: 'done', report }, graph: target });
    } catch (error) {
      if (serial !== requestSerial.current) return;
      const unavailable = error instanceof StudioError && error.kind === 'unavailable';
      if (unavailable) setAutomatic(false);
      setValidated({ view: { status: unavailable ? 'unavailable' : 'failed' }, graph: null });
    }
    setValidating(false);
  };

  const latest = useRef(validate);
  useEffect(() => {
    latest.current = validate;
  });
  useEffect(() => {
    if (readOnly || !automatic || graph.nodes.length === 0) return;
    const timer = setTimeout(() => void latest.current(graph), VALIDATION_DELAY_MS);
    return () => clearTimeout(timer);
  }, [graph, readOnly, automatic]);

  const stale = validated.view.status === 'done' && validated.graph !== graph;
  return { validated, validating, stale, validate };
}
