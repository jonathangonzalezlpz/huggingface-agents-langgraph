import { AlertTriangle } from 'lucide-react';

import { StudioError } from '../../domain/errors';
import { useI18n } from '../../i18n/I18nProvider';

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  let message = t('error.contract');
  if (error instanceof StudioError) {
    if (error.kind === 'network') message = t('error.network');
    else if (error.kind === 'http') message = t('error.http', { status: error.status ?? '?' });
  }
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-line-strong bg-error-soft p-4 text-error"
    >
      <AlertTriangle aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div className="flex flex-1 flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold">{t('error.title')}</p>
          <p className="text-sm">{message}</p>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="min-h-8 rounded-lg border border-current px-3 text-sm font-medium hover:bg-surface/40"
          >
            {t('common.retry')}
          </button>
        )}
      </div>
    </div>
  );
}
