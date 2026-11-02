import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

import type { SystemStatus } from '../../domain/types';
import { useServices } from '../services';

const POLL_INTERVAL_MS = 30_000;

const SystemStatusContext = createContext<SystemStatus | null>(null);

/** Polls the backend status and shares the latest value with the shell and pages. */
export function SystemStatusProvider({ children }: { children: ReactNode }) {
  const { system } = useServices();
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    let active = true;
    const poll = () => {
      system.getStatus().then(
        (next) => {
          if (active) setStatus(next);
        },
        () => undefined,
      );
    };
    poll();
    const timer = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [system]);

  return <SystemStatusContext.Provider value={status}>{children}</SystemStatusContext.Provider>;
}

/** Latest known status, or null until the first response arrives. */
export function useSystemStatus(): SystemStatus | null {
  return useContext(SystemStatusContext);
}
