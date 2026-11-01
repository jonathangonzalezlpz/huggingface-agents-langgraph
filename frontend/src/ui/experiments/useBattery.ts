import { useCallback, useEffect, useRef, useState } from 'react';

import {
  IDLE_BATTERY,
  isBatteryActive,
  type BatteryRequest,
  type BatteryStatus,
} from '../../domain/battery';
import type { BatteryPort } from '../../ports';

export const POLL_INTERVAL_MS = 2000;

/**
 * Follow the server's battery: read it on mount, poll while it works, and expose start and stop.
 * `onFinished` fires once each time a battery goes from active to not active.
 */
export function useBattery(
  batteries: BatteryPort,
  options: { onFinished?: () => void; pollMs?: number } = {},
) {
  const { onFinished, pollMs = POLL_INTERVAL_MS } = options;
  const [status, setStatus] = useState<BatteryStatus>(IDLE_BATTERY);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const wasActive = useRef(false);
  const finished = useRef(onFinished);
  useEffect(() => {
    finished.current = onFinished;
  }, [onFinished]);

  const apply = useCallback((next: BatteryStatus) => {
    const active = isBatteryActive(next);
    if (wasActive.current && !active) finished.current?.();
    wasActive.current = active;
    setStatus(next);
  }, []);

  useEffect(() => {
    let alive = true;
    batteries.current().then(
      (next) => {
        if (!alive) return;
        apply(next);
        setLoaded(true);
      },
      (error: unknown) => {
        if (!alive) return;
        setActionError(error);
        setLoaded(true);
      },
    );
    return () => {
      alive = false;
    };
  }, [batteries, apply]);

  const active = isBatteryActive(status);
  useEffect(() => {
    if (!active) return;
    let alive = true;
    const timer = setInterval(() => {
      batteries.current().then(
        (next) => alive && apply(next),
        // A missed poll is not a failure: the battery keeps running on the server.
        () => undefined,
      );
    }, pollMs);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [active, batteries, apply, pollMs]);

  const run = useCallback(
    async (action: () => Promise<BatteryStatus>) => {
      setBusy(true);
      setActionError(null);
      try {
        apply(await action());
      } catch (error) {
        setActionError(error);
      } finally {
        setBusy(false);
      }
    },
    [apply],
  );

  const start = useCallback(
    (request: BatteryRequest) => run(() => batteries.start(request)),
    [batteries, run],
  );
  const stop = useCallback(() => run(() => batteries.stop()), [batteries, run]);

  return { status, loaded, busy, actionError, start, stop };
}
