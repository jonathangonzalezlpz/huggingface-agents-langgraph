import { FlaskConical, Play, Settings2, Workflow } from 'lucide-react';
import type { ComponentType } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n';
import { useServices } from '../services';
import { LanguageToggle, ThemeToggle } from './Preferences';
import { StatusPanel } from './StatusPanel';
import { SystemStatusProvider, useSystemStatus } from './SystemStatusProvider';

const NAVIGATION: {
  to: string;
  label: MessageKey;
  Icon: ComponentType<{ className?: string }>;
}[] = [
  { to: '/builder', label: 'nav.builder', Icon: Workflow },
  { to: '/runs', label: 'nav.runs', Icon: Play },
  { to: '/experiments', label: 'nav.experiments', Icon: FlaskConical },
  { to: '/system', label: 'nav.system', Icon: Settings2 },
];

function Sidebar() {
  const { t } = useI18n();
  const status = useSystemStatus();
  return (
    <aside className="flex flex-col gap-6 border-b border-line bg-surface p-4 md:sticky md:top-0 md:h-screen md:w-64 md:shrink-0 md:overflow-y-auto md:border-r md:border-b-0">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-on-accent"
        >
          <Workflow className="size-5" />
        </span>
        <div>
          <p className="font-semibold leading-tight">{t('app.name')}</p>
          <p className="text-xs leading-snug text-fg-muted">{t('app.tagline')}</p>
        </div>
      </div>

      <nav aria-label={t('nav.label')}>
        <ul className="flex gap-1 md:flex-col">
          {NAVIGATION.map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium ${
                    isActive
                      ? 'bg-accent-soft text-accent-fg'
                      : 'text-fg-muted hover:bg-muted hover:text-fg'
                  }`
                }
              >
                <Icon aria-hidden="true" className="size-4 shrink-0" />
                {t(label)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-5 md:mt-auto">
        <StatusPanel status={status} />
        <div className="flex flex-wrap gap-2">
          <ThemeToggle />
          <LanguageToggle />
        </div>
      </div>
    </aside>
  );
}

export function AppShell() {
  const { t } = useI18n();
  const { mode } = useServices();
  const fullBleed = useLocation().pathname.startsWith('/builder/');
  return (
    <SystemStatusProvider>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-on-accent"
      >
        {t('skip.toContent')}
      </a>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar />
        <div className="min-w-0 flex-1">
          {mode === 'demo' && (
            <p
              role="status"
              className="border-b border-line bg-warning-soft px-6 py-2 text-sm text-warning"
            >
              {t('demo.banner')}
            </p>
          )}
          <main
            id="main"
            tabIndex={-1}
            className={fullBleed ? '' : 'mx-auto max-w-5xl p-6 md:p-10'}
          >
            <Outlet />
          </main>
        </div>
      </div>
    </SystemStatusProvider>
  );
}
