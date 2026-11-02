import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';

import type { StudioServices } from '../ports';

const ServicesContext = createContext<StudioServices | null>(null);

export function ServicesProvider({
  services,
  children,
}: {
  services: StudioServices;
  children: ReactNode;
}) {
  return <ServicesContext.Provider value={services}>{children}</ServicesContext.Provider>;
}

export function useServices(): StudioServices {
  const services = useContext(ServicesContext);
  if (!services) throw new Error('useServices must be used inside ServicesProvider');
  return services;
}
