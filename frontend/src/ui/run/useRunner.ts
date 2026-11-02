import { useCallback, useEffect, useRef, useState } from 'react';

import { StudioError } from '../../domain/errors';
import type { RunRecord, RunRequest } from '../../domain/run';
import type { RunPort } from '../../ports';

export type RunState =
  | { status: 'idle' }
  | { status: 'running' }
  | { status: 'stopped' }
  | { status: 'done'; record: RunRecord }
  | { status: 'failed'; error: unknown };

const TICK_MS = 1000;

/** One run at a time, with the seconds waited so far and a way to stop waiting. */
export function useRunner(runs: RunPort) {
  const [state, setState] = useState<RunState>({ status: 'idle' });
  const [elapsed, setElapsed] = useState(0);
  const controller = useRef<AbortController | null>(null);
  const running = state.status === 'running';

  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / TICK_MS)),
      TICK_MS,
    );
    return () => clearInterval(timer);
  }, [running]);

  const start = useCallback(
    async (request: RunRequest) => {
      controller.current?.abort();
      const own = new AbortController();
      controller.current = own;
      setElapsed(0);
      setState({ status: 'running' });
      try {
        const record = await runs.run(request, own.signal);
        if (controller.current === own) setState({ status: 'done', record });
      } catch (error) {
        if (controller.current !== own) return;
        if (error instanceof StudioError && error.kind === 'aborted')
          setState({ status: 'stopped' });
        else setState({ status: 'failed', error });
      }
    },
    [runs],
  );

  /** The server cannot cancel a run: this only stops waiting for its answer. */
  const stopWaiting = useCallback(() => controller.current?.abort(), []);

  return { state, elapsed, start, stopWaiting };
}
