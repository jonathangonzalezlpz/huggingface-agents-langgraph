import * as Dialog from '@radix-ui/react-dialog';
import { Trash2 } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  MAX_COMPARED,
  MIN_COMPARED,
  filterHistory,
  sortHistory,
  type ExperimentRecord,
  type HistorySort,
} from '../../domain/history';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { StatusBadge, type Tone } from '../components/StatusBadge';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { ComparisonView } from './ComparisonView';
import { formatDate, formatScore, formatSeconds } from './format';

const FIELD = 'min-h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm';
const CELL = 'border-b border-line px-3 py-2 text-left text-sm';
const HEAD = `${CELL} font-medium text-fg-muted`;
const BUTTON =
  'inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50';

const STATUS_TONE: Record<string, Tone> = {
  completed: 'success',
  cancelled: 'warning',
  running: 'info',
};
const STATUS_KEY: Record<string, MessageKey> = {
  completed: 'history.status.completed',
  cancelled: 'history.status.cancelled',
  running: 'history.status.running',
};

export function ArchitectureLabel({ value }: { value: string | null }) {
  const { t } = useI18n();
  if (value === null) return <span className="text-fg-muted">—</span>;
  return (
    <span className="font-mono text-xs">
      {value === 'builtin:gaia_v31' ? t('history.architecture.builtin') : value}
    </span>
  );
}

export function ExperimentStatus({ status }: { status: string }) {
  const { t } = useI18n();
  const key = STATUS_KEY[status];
  return <StatusBadge tone={STATUS_TONE[status] ?? 'neutral'}>{key ? t(key) : status}</StatusBadge>;
}

function DeleteDialog({
  record,
  onClose,
  onDeleted,
}: {
  record: ExperimentRecord | null;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { t } = useI18n();
  const { experiments } = useServices();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const confirm = async () => {
    if (!record) return;
    setBusy(true);
    setFailed(false);
    try {
      await experiments.remove(record.id);
      onDeleted();
      onClose();
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog.Root open={record !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          aria-describedby="delete-body"
          className="fixed top-24 left-1/2 z-50 w-[min(28rem,92vw)] -translate-x-1/2 rounded-xl border border-line-strong bg-surface p-5 text-fg shadow-xl"
        >
          <Dialog.Title className="text-base font-semibold">
            {t('history.delete.title')}
          </Dialog.Title>
          <Dialog.Description id="delete-body" className="mt-2 text-sm">
            {t('history.delete.body', { name: record?.name ?? '' })}
          </Dialog.Description>
          {failed && (
            <p role="alert" className="mt-2 text-sm text-error">
              {t('history.delete.failed')}
            </p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" className={BUTTON} onClick={onClose}>
              {t('history.delete.cancel')}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void confirm()}
              className={`${BUTTON} border-transparent bg-error text-on-accent`}
            >
              {t('history.delete.confirm')}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function HistoryPage() {
  const { t, tp, language } = useI18n();
  const { experiments } = useServices();
  const state = useAsyncData(useCallback(() => experiments.list(), [experiments]));
  const { reload } = state;

  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<HistorySort>('newest');
  const [selected, setSelected] = useState<string[]>([]);
  const [base, setBase] = useState<string | null>(null);
  const [comparing, setComparing] = useState<string[] | null>(null);
  const [deleting, setDeleting] = useState<ExperimentRecord | null>(null);

  const records = useMemo(() => (state.status === 'success' ? state.data : []), [state]);
  const visible = useMemo(
    () => sortHistory(filterHistory(records, query), sort),
    [records, query, sort],
  );
  const chosen = selected.filter((id) => records.some((record) => record.id === id));
  const canCompare = chosen.length >= MIN_COMPARED && chosen.length <= MAX_COMPARED;
  const effectiveBase = base !== null && chosen.includes(base) ? base : (chosen[0] ?? null);

  const toggle = (id: string) => {
    setComparing(null);
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  if (state.status === 'loading') return <p className="text-fg-muted">{t('common.loading')}</p>;
  if (state.status === 'error') return <ErrorNotice error={state.error} onRetry={state.reload} />;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">{t('history.title')}</h2>

      {records.length === 0 ? (
        <p className="text-fg-muted">{t('history.empty')}</p>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label htmlFor="history-search" className="mb-1 block text-sm font-medium">
                {t('history.search')}
              </label>
              <input
                id="history-search"
                className={`${FIELD} w-64`}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="history-sort" className="mb-1 block text-sm font-medium">
                {t('history.sort')}
              </label>
              <select
                id="history-sort"
                className={FIELD}
                value={sort}
                onChange={(event) => setSort(event.target.value as HistorySort)}
              >
                <option value="newest">{t('history.sort.newest')}</option>
                <option value="score">{t('history.sort.score')}</option>
                <option value="speed">{t('history.sort.speed')}</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[48rem] border-collapse">
              <thead>
                <tr>
                  <th className={HEAD}>
                    <span className="sr-only">{t('history.col.select')}</span>
                  </th>
                  <th className={HEAD}>{t('history.col.name')}</th>
                  <th className={HEAD}>{t('history.col.version')}</th>
                  <th className={HEAD}>{t('history.col.architecture')}</th>
                  <th className={HEAD}>{t('history.col.status')}</th>
                  <th className={HEAD}>{t('history.col.score')}</th>
                  <th className={HEAD}>{t('history.col.official')}</th>
                  <th className={HEAD}>{t('history.col.time')}</th>
                  <th className={HEAD}>{t('history.col.date')}</th>
                  <th className={HEAD}>
                    <span className="sr-only">{t('history.delete')}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={10} className={`${CELL} text-fg-muted`}>
                      {t('history.noMatches')}
                    </td>
                  </tr>
                )}
                {visible.map((record) => (
                  <tr key={record.id}>
                    <td className={CELL}>
                      <input
                        type="checkbox"
                        aria-label={t('history.select', { name: record.name })}
                        checked={chosen.includes(record.id)}
                        onChange={() => toggle(record.id)}
                      />
                    </td>
                    <th scope="row" className={`${CELL} font-medium`}>
                      <Link
                        to={`/experiments/${encodeURIComponent(record.id)}`}
                        className="text-accent-fg underline underline-offset-2"
                      >
                        {record.name}
                      </Link>
                    </th>
                    <td className={CELL}>{record.pipelineVersion ?? '—'}</td>
                    <td className={CELL}>
                      <ArchitectureLabel value={record.architecture} />
                    </td>
                    <td className={CELL}>
                      <ExperimentStatus status={record.status} />
                    </td>
                    <td className={CELL}>
                      {record.localScore
                        ? t('history.score.value', formatScore(record.localScore))
                        : t('history.score.none')}
                    </td>
                    <td className={CELL}>
                      {record.officialScore
                        ? t('history.score.value', formatScore(record.officialScore))
                        : '—'}
                    </td>
                    <td className={CELL}>{formatSeconds(record.averageSeconds)}</td>
                    <td className={CELL}>{formatDate(record.createdAt, language)}</td>
                    <td className={CELL}>
                      <button
                        type="button"
                        onClick={() => setDeleting(record)}
                        className="inline-flex size-8 items-center justify-center rounded-lg text-fg-muted hover:bg-muted hover:text-error"
                        aria-label={`${t('history.delete')}: ${record.name}`}
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              disabled={!canCompare}
              onClick={() => setComparing(chosen)}
              className={BUTTON}
            >
              {t('history.compare')}
            </button>
            <span role="status" className="text-sm text-fg-muted">
              {chosen.length > 0
                ? tp('history.selected', chosen.length)
                : t('history.compare.hint')}
            </span>
            {canCompare && (
              <div className="flex items-center gap-2">
                <label htmlFor="compare-base" className="text-sm font-medium">
                  {t('history.compare.base')}
                </label>
                <select
                  id="compare-base"
                  className={FIELD}
                  value={effectiveBase ?? ''}
                  onChange={(event) => {
                    setComparing(null);
                    setBase(event.target.value);
                  }}
                >
                  {chosen.map((id) => (
                    <option key={id} value={id}>
                      {records.find((record) => record.id === id)?.name ?? id}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </>
      )}

      {comparing && <ComparisonView ids={comparing} base={effectiveBase} records={records} />}

      <DeleteDialog
        record={deleting}
        onClose={() => setDeleting(null)}
        onDeleted={() => {
          setSelected((current) => current.filter((id) => id !== deleting?.id));
          setComparing(null);
          reload();
        }}
      />
    </div>
  );
}
