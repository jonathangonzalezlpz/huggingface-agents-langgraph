import { Link } from 'react-router-dom';

import { useI18n } from '../../i18n/I18nProvider';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { gpuLabel, modelLabel } from '../shell/StatusPanel';
import { useServices } from '../services';
import { useSystemStatus } from '../shell/SystemStatusProvider';

export function SystemPage() {
  const { t } = useI18n();
  const { mode } = useServices();
  const status = useSystemStatus();
  const model = modelLabel(status);
  const gpu = gpuLabel(status);
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
        <div className="flex items-center justify-between gap-4 p-4">
          <dt className="text-fg-muted">{t('system.gpu')}</dt>
          <dd className="text-right">
            <StatusBadge tone={gpu.tone}>{t(gpu.key)}</StatusBadge>
            {status?.gpu?.available && (
              <p className="mt-1 text-xs text-fg-muted">
                {[status.gpu.name, status.gpu.backend].filter(Boolean).join(' · ')}
              </p>
            )}
          </dd>
        </div>
        {status?.hostMemory && (
          <div className="flex items-center justify-between gap-4 p-4">
            <dt className="text-fg-muted">{t('system.memory')}</dt>
            <dd>
              {t('system.memory.value', {
                available: status.hostMemory.availableMib,
                total: status.hostMemory.totalMib,
              })}
            </dd>
          </div>
        )}
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
