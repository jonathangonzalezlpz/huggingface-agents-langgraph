import { Link } from 'react-router-dom';

import { useI18n } from '../../i18n/I18nProvider';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { modelLabel } from '../shell/StatusPanel';
import { useServices } from '../services';
import { useSystemStatus } from '../shell/SystemStatusProvider';

export function SystemPage() {
  const { t } = useI18n();
  const { mode } = useServices();
  const model = modelLabel(useSystemStatus());
  return (
    <>
      <PageHeader title={t('system.title')} description={t('system.description')} />
      <dl className="max-w-xl divide-y divide-line rounded-xl border border-line bg-surface">
        <div className="flex items-center justify-between gap-4 p-4">
          <dt className="text-fg-muted">{t('system.mode')}</dt>
          <dd className="font-medium">
            {mode === 'live' ? t('system.mode.live') : t('system.mode.demo')}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-4 p-4">
          <dt className="text-fg-muted">{t('system.model')}</dt>
          <dd>
            <StatusBadge tone={model.tone}>{t(model.key)}</StatusBadge>
          </dd>
        </div>
      </dl>
    </>
  );
}

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t('notfound.title')} description={t('notfound.body')} />
      <Link to="/builder" className="text-accent-fg underline underline-offset-2">
        {t('notfound.back')}
      </Link>
    </>
  );
}
