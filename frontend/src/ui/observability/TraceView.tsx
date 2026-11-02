import { AlertTriangle } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import {
  formatDuration,
  traceExports,
  waterfallRows,
  type SpanKind,
  type Trace,
  type WaterfallRow,
} from '../../domain/trace';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { ExportLinks } from './ExportLinks';
import { SpanDetail } from './SpanDetail';

const KINDS: { kind: SpanKind; label: MessageKey }[] = [
  { kind: 'run', label: 'obs.filter.run' },
  { kind: 'node', label: 'obs.filter.node' },
  { kind: 'llm', label: 'obs.filter.llm' },
];
const BAR_COLOR: Record<SpanKind, string> = {
  run: 'bg-muted',
  node: 'bg-accent',
  llm: 'bg-info',
};

function Summary({ trace }: { trace: Trace }) {
  const { t } = useI18n();
  const { summary } = trace;
  const items: [MessageKey, string][] = [
    [
      'obs.summary.duration',
      summary.durationSeconds === null ? '—' : formatDuration(summary.durationSeconds),
    ],
    ['obs.summary.calls', String(summary.llmCalls)],
    ['obs.summary.tokens', `${summary.promptTokens} / ${summary.completionTokens}`],
    ['obs.summary.errors', String(summary.errorCount)],
    [
      'obs.summary.slowest',
      summary.slowestNode
        ? `${summary.slowestNode.name} (${formatDuration(summary.slowestNode.durationSeconds)})`
        : '—',
    ],
  ];
  return (
    <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs font-medium text-fg-muted">{t(label)}</dt>
          <dd className="mt-0.5 text-sm">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Row({
  row,
  selected,
  onSelect,
}: {
  row: WaterfallRow;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useI18n();
  const { span } = row;
  const failed = span.status === 'error';
  return (
    <li>
      <button
        type="button"
        aria-label={t('obs.waterfall.open', { name: span.name })}
        aria-pressed={selected}
        onClick={onSelect}
        className={`grid w-full grid-cols-[minmax(9rem,16rem)_1fr_5rem] items-center gap-3 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-muted ${
          selected ? 'bg-accent-soft' : ''
        }`}
      >
        <span className="min-w-0" style={{ paddingLeft: `${row.depth * 1.25}rem` }}>
          <span className={`flex items-center gap-1.5 truncate ${failed ? 'text-error' : ''}`}>
            {span.kind === 'llm' ? t('obs.waterfall.llm') : span.name}
            {span.attributes['unsupported_figures'] ? (
              <AlertTriangle aria-hidden="true" className="size-3.5 shrink-0 text-warning" />
            ) : null}
          </span>
          {typeof span.attributes['activity'] === 'string' && (
            <span className="block truncate text-xs text-fg-muted">
              {span.attributes['activity']}
            </span>
          )}
        </span>
        <span aria-hidden="true" className="relative h-3 rounded bg-muted/50">
          <span
            className={`absolute inset-y-0 rounded ${failed ? 'bg-error' : BAR_COLOR[span.kind]}`}
            style={{ left: `${row.leftPercent}%`, width: `${row.widthPercent}%` }}
          />
        </span>
        <span className="text-right text-fg-muted">{formatDuration(span.durationSeconds)}</span>
      </button>
    </li>
  );
}

function Filters({
  kinds,
  onlyErrors,
  onKinds,
  onOnlyErrors,
}: {
  kinds: SpanKind[];
  onlyErrors: boolean;
  onKinds: (kinds: SpanKind[]) => void;
  onOnlyErrors: (value: boolean) => void;
}) {
  const { t } = useI18n();
  const toggle = (kind: SpanKind) =>
    onKinds(kinds.includes(kind) ? kinds.filter((item) => item !== kind) : [...kinds, kind]);
  return (
    <fieldset className="flex flex-wrap items-center gap-4">
      <legend className="sr-only">{t('obs.filter.label')}</legend>
      {KINDS.map(({ kind, label }) => (
        <label key={kind} className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={kinds.includes(kind)} onChange={() => toggle(kind)} />
          {t(label)}
        </label>
      ))}
      <label className="inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={onlyErrors}
          onChange={(event) => onOnlyErrors(event.target.checked)}
        />
        {t('obs.filter.errors')}
      </label>
    </fieldset>
  );
}

/** The trace of one run: summary, waterfall of spans, exports and the content of a chosen span. */
export function TraceView({ runId }: { runId: string }) {
  const { t } = useI18n();
  const { traces } = useServices();
  const state = useAsyncData(useCallback(() => traces.getTrace(runId), [traces, runId]));
  const [kinds, setKinds] = useState<SpanKind[]>(['run', 'node', 'llm']);
  const [onlyErrors, setOnlyErrors] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const data = state.status === 'success' ? state.data : null;
  const rows = useMemo(
    () => (data ? waterfallRows(data, { kinds, onlyErrors }) : []),
    [data, kinds, onlyErrors],
  );

  if (state.status === 'loading') return <p className="text-fg-muted">{t('obs.loading')}</p>;
  if (state.status === 'error') return <ErrorNotice error={state.error} onRetry={state.reload} />;

  const trace = state.data;
  const selected = trace.spans.find((span) => span.id === selectedId) ?? null;
  const legacy = trace.spans.some((span) => span.attributes['linked_to_node'] === false);
  const inferred = !legacy && trace.spans.some((span) => span.attributes['inferred_link'] === true);
  return (
    <div className="space-y-5">
      <Summary trace={trace} />
      {legacy && (
        <p className="rounded-lg bg-warning-soft p-3 text-sm text-warning">{t('obs.legacy')}</p>
      )}
      {inferred && (
        <p className="rounded-lg bg-info-soft p-3 text-sm text-info">{t('obs.inferred')}</p>
      )}
      {trace.summary.unsupportedFigures.length > 0 && (
        <p className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          {t('obs.unsupported', { figures: trace.summary.unsupportedFigures.join(', ') })}
        </p>
      )}
      <ExportLinks links={traceExports(trace.id)} />
      <section aria-labelledby="waterfall-heading" className="space-y-2">
        <h3 id="waterfall-heading" className="font-semibold">
          {t('obs.waterfall.title')}
        </h3>
        <Filters
          kinds={kinds}
          onlyErrors={onlyErrors}
          onKinds={setKinds}
          onOnlyErrors={setOnlyErrors}
        />
        {rows.length === 0 ? (
          <p className="text-fg-muted">{t('obs.waterfall.empty')}</p>
        ) : (
          <ul className="space-y-0.5">
            {rows.map((row) => (
              <Row
                key={row.span.id}
                row={row}
                selected={row.span.id === selectedId}
                onSelect={() => setSelectedId(row.span.id)}
              />
            ))}
          </ul>
        )}
      </section>
      {selected && (
        <SpanDetail runId={trace.id} span={selected} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
