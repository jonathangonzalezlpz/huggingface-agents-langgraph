import { X } from 'lucide-react';
import { useCallback } from 'react';

import type { Span } from '../../domain/trace';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';

const ATTRIBUTE_LABELS: Record<string, MessageKey> = {
  model: 'obs.attr.model',
  prompt_tokens: 'obs.attr.prompt_tokens',
  completion_tokens: 'obs.attr.completion_tokens',
  cached_tokens: 'obs.attr.cached_tokens',
  finish_reason: 'obs.attr.finish_reason',
  max_tokens: 'obs.attr.max_tokens',
  temperature: 'obs.attr.temperature',
  updated_fields: 'obs.attr.updated_fields',
  activity: 'obs.attr.activity',
  unsupported_figures: 'obs.attr.unsupported_figures',
};

function Payload({ runId, spanId }: { runId: string; spanId: string }) {
  const { t } = useI18n();
  const { traces } = useServices();
  const state = useAsyncData(
    useCallback(() => traces.getSpanPayload(runId, spanId), [traces, runId, spanId]),
  );
  if (state.status === 'loading') return <p className="text-fg-muted">{t('obs.detail.loading')}</p>;
  if (state.status === 'error') return <ErrorNotice error={state.error} onRetry={state.reload} />;
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-3 text-xs whitespace-pre-wrap">
      {JSON.stringify(state.data, null, 2)}
    </pre>
  );
}

/** The attributes of a span and, loaded on demand, its heavy content. */
export function SpanDetail({
  runId,
  span,
  onClose,
}: {
  runId: string;
  span: Span;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const attributes = Object.entries(span.attributes).filter(([key]) => key in ATTRIBUTE_LABELS);
  return (
    <section
      aria-labelledby="span-detail-heading"
      className="space-y-3 rounded-xl border border-line p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 id="span-detail-heading" className="font-semibold">
          {t('obs.detail.title', { name: span.name })}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-line-strong px-2.5 text-sm"
        >
          <X aria-hidden="true" className="size-4" />
          {t('obs.detail.close')}
        </button>
      </div>
      {span.error && (
        <p role="alert" className="text-sm text-error">
          {t('obs.detail.error', { message: span.error })}
        </p>
      )}
      {attributes.length > 0 && (
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {attributes.map(([key, value]) => (
            <div key={key}>
              <dt className="text-xs font-medium text-fg-muted">
                {t(ATTRIBUTE_LABELS[key] as MessageKey)}
              </dt>
              <dd className="mt-0.5 text-sm break-words">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      <Payload runId={runId} spanId={span.id} />
    </section>
  );
}
