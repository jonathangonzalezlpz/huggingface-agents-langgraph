import { NavLink, Outlet } from 'react-router-dom';

import { useI18n } from '../../i18n/I18nProvider';
import { PageHeader } from '../components/PageHeader';

const TAB = 'inline-flex min-h-10 items-center border-b-2 px-4 text-sm font-medium -mb-px';

/** Shared frame of the experiments area: title and a switch between batteries and history. */
export function ExperimentsLayout() {
  const { t } = useI18n();
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `${TAB} ${
      isActive ? 'border-accent text-accent-fg' : 'border-transparent text-fg-muted hover:text-fg'
    }`;
  return (
    <>
      <PageHeader title={t('experiments.title')} description={t('experiments.description')} />
      <nav aria-label={t('experiments.tabs')} className="mb-8 flex border-b border-line">
        <NavLink to="/experiments" end className={tabClass}>
          {t('experiments.tab.battery')}
        </NavLink>
        <NavLink to="/experiments/history" className={tabClass}>
          {t('experiments.tab.history')}
        </NavLink>
      </nav>
      <Outlet />
    </>
  );
}
