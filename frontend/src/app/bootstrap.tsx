import { BrowserRouter, HashRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

import { createHttpServices } from '../adapters/http/httpServices';
import { createMemoryServices } from '../adapters/memory/memoryServices';
import { I18nProvider } from '../i18n/I18nProvider';
import type { StudioMode, StudioServices } from '../ports';
import { ThemeProvider } from '../theme/ThemeProvider';
import { ServicesProvider } from '../ui/services';
import { AppRoutes } from './AppRoutes';

/** Demo mode comes from the build or from `?demo=1`; otherwise the real backend is used. */
export function chooseMode(search: string, buildMode: string | undefined): StudioMode {
  return buildMode === 'demo' || new URLSearchParams(search).get('demo') === '1' ? 'demo' : 'live';
}

export function createServices(mode: StudioMode): StudioServices {
  return mode === 'demo' ? createMemoryServices() : createHttpServices();
}

/** Providers shared by the real app and by tests, with the router supplied by the caller. */
export function StudioProviders({
  services,
  children,
}: {
  services: StudioServices;
  children: ReactNode;
}) {
  return (
    <ThemeProvider>
      <I18nProvider>
        <ServicesProvider services={services}>{children}</ServicesProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}

export function StudioApp({ services }: { services: StudioServices }) {
  // A static host (the public Space) cannot rewrite client routes, so demo mode uses the hash.
  const Router = services.mode === 'demo' ? HashRouter : BrowserRouter;
  const routerProps = services.mode === 'demo' ? {} : { basename: '/app' };
  return (
    <StudioProviders services={services}>
      <Router {...routerProps}>
        <AppRoutes />
      </Router>
    </StudioProviders>
  );
}
