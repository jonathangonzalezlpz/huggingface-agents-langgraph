import * as Dialog from '@radix-ui/react-dialog';
import { Paperclip } from 'lucide-react';
import { useCallback, useState } from 'react';

import type { GaiaQuestion } from '../../domain/run';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';

const OVERLAY = 'fixed inset-0 z-40 bg-black/50';
const CONTENT =
  'fixed top-16 left-1/2 z-50 w-[min(40rem,94vw)] -translate-x-1/2 rounded-xl border border-line-strong bg-surface p-5 text-fg shadow-xl';

function Questions({ onPick }: { onPick: (question: GaiaQuestion) => void }) {
  const { t } = useI18n();
  const { questions } = useServices();
  const [query, setQuery] = useState('');
  const load = useCallback(() => questions.list(), [questions]);
  const state = useAsyncData(load);

  if (state.status === 'loading') return <p className="text-fg-muted">{t('runs.gaia.loading')}</p>;
  if (state.status === 'error') {
    return <ErrorNotice error={state.error} onRetry={state.reload} />;
  }
  const needle = query.trim().toLowerCase();
  const matches = state.data.filter((item) => item.question.toLowerCase().includes(needle));

  return (
    <>
      <input
        aria-label={t('runs.gaia.search')}
        value={query}
        placeholder={t('runs.gaia.search')}
        onChange={(event) => setQuery(event.target.value)}
        className="min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm"
      />
      <ul className="mt-3 max-h-80 space-y-1.5 overflow-y-auto">
        {matches.length === 0 && <li className="text-sm text-fg-muted">{t('runs.gaia.empty')}</li>}
        {matches.map((item) => (
          <li key={item.taskId}>
            <button
              type="button"
              onClick={() => onPick(item)}
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm hover:bg-muted"
            >
              <span className="line-clamp-2">{item.question}</span>
              <span className="mt-1 flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                <span>{t('runs.gaia.level', { level: item.level })}</span>
                {item.fileName && (
                  <span className="inline-flex items-center gap-1">
                    <Paperclip aria-hidden="true" className="size-3" />
                    {t('runs.gaia.attachment', { file: item.fileName })}
                  </span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Choose one of the GAIA validation questions. Only offered with a live backend. */
export function GaiaPicker({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (question: GaiaQuestion) => void;
}) {
  const { t } = useI18n();
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className={OVERLAY} />
        <Dialog.Content aria-describedby={undefined} className={CONTENT}>
          <Dialog.Title className="mb-3 text-base font-semibold">
            {t('runs.gaia.title')}
          </Dialog.Title>
          <Questions
            onPick={(question) => {
              onPick(question);
              onClose();
            }}
          />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
