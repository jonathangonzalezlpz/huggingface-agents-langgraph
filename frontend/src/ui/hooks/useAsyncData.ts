import { useCallback, useEffect, useState } from 'react';

export type AsyncState<T> =
  { status: 'loading' } | { status: 'error'; error: unknown } | { status: 'success'; data: T };

/**
 * Load data when `load` changes (keep it referentially stable) and on demand.
 * Results of superseded requests are discarded.
 */
export function useAsyncData<T>(load: () => Promise<T>): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    load().then(
      (data) => {
        if (active) setState({ status: 'success', data });
      },
      (error: unknown) => {
        if (active) setState({ status: 'error', error });
      },
    );
    return () => {
      active = false;
    };
  }, [load, attempt]);

  const reload = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((current) => current + 1);
  }, []);

  return { ...state, reload };
}
