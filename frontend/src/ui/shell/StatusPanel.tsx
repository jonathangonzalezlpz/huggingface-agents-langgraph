import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n';
import type { LlmState, SystemStatus } from '../../domain/types';
import { StatusBadge, type Tone } from '../components/StatusBadge';

const MODEL_TONES: Record<LlmState, Tone> = {
  ready: 'success',
  sleeping: 'info',
  loading: 'warning',
  unavailable: 'error',
};

export function backendLabel(status: SystemStatus | null): { tone: Tone; key: MessageKey } {
  if (status === null) return { tone: 'neutral', key: 'common.loading' };
  return status.backend === 'online'
    ? { tone: 'success', key: 'status.backend.online' }
    : { tone: 'error', key: 'status.backend.offline' };
}

export function modelLabel(status: SystemStatus | null): { tone: Tone; key: MessageKey } {
  if (status?.llm == null) return { tone: 'neutral', key: 'status.model.unknown' };
  return { tone: MODEL_TONES[status.llm.state], key: `status.model.${status.llm.state}` };
}

export function StatusPanel({ status }: { status: SystemStatus | null }) {
  const { t } = useI18n();
  const backend = backendLabel(status);
  const model = modelLabel(status);
  return (
    <section aria-labelledby="status-heading">
      <h2
        id="status-heading"
        className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted"
      >
        {t('status.title')}
      </h2>
      <dl className="space-y-2 text-sm">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-fg-muted">{t('status.backend')}</dt>
          <dd>
            <StatusBadge tone={backend.tone}>{t(backend.key)}</StatusBadge>
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-fg-muted">{t('status.model')}</dt>
          <dd>
            <StatusBadge tone={model.tone}>{t(model.key)}</StatusBadge>
          </dd>
        </div>
      </dl>
    </section>
  );
}
