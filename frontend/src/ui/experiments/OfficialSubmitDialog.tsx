import * as Dialog from '@radix-ui/react-dialog';
import { useState } from 'react';

import { StudioError } from '../../domain/errors';
import { QUESTION_COUNT, submissionIssue, type ExperimentRecord } from '../../domain/history';
import type { MessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { useServices } from '../services';
import { formatScore } from './format';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';
const BUTTON =
  'inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50';

function errorKey(error: unknown): MessageKey {
  if (error instanceof StudioError && error.kind === 'http') {
    if (error.status === 502) return 'official.error.unreachable';
    if (error.status === 400 || error.status === 404) return 'official.error.invalid';
  }
  if (error instanceof StudioError && error.kind === 'network') {
    return 'official.error.unreachable';
  }
  return 'official.error.generic';
}

/**
 * The only way to publish a result to the official evaluator. Nothing leaves the machine until
 * the user has filled both fields, read what will be sent, and ticked the acknowledgement.
 */
export function OfficialSubmitDialog({
  record,
  open,
  onClose,
  onSent,
}: {
  record: ExperimentRecord;
  open: boolean;
  onClose: () => void;
  onSent: () => void;
}) {
  const { t } = useI18n();
  const { experiments } = useServices();
  const [username, setUsername] = useState('');
  const [agentCode, setAgentCode] = useState('');
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const [sent, setSent] = useState<{ text: string; saved: boolean } | null>(null);

  const complete = record.answers.length === QUESTION_COUNT;
  const ready = complete && submissionIssue(username, agentCode) === null && understood && !busy;

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await experiments.submitOfficial({
        experimentId: record.id,
        username: username.trim(),
        agentCode: agentCode.trim(),
      });
      setSent({ text: t('official.sent', formatScore(result.score)), saved: result.saved });
    } catch (failure) {
      setError(errorKey(failure));
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    // Refresh the experiment only now: reloading earlier would unmount this dialog and its result.
    if (sent) onSent();
    setUnderstood(false);
    setError(null);
    setSent(null);
    onClose();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && close()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          aria-describedby="official-warning"
          className="fixed top-16 left-1/2 z-50 w-[min(34rem,94vw)] -translate-x-1/2 rounded-xl border border-line-strong bg-surface p-5 text-fg shadow-xl"
        >
          <Dialog.Title className="text-base font-semibold">
            {t('official.dialog.title')}
          </Dialog.Title>
          <Dialog.Description
            id="official-warning"
            className="mt-2 rounded-lg border border-line-strong bg-warning-soft p-3 text-sm"
          >
            {t('official.warning')}
          </Dialog.Description>

          {sent ? (
            <div className="mt-4 space-y-2">
              <p role="status" className="font-medium">
                {sent.text}
              </p>
              {!sent.saved && (
                <p role="alert" className="text-sm text-warning">
                  {t('official.notSaved')}
                </p>
              )}
              <div className="flex justify-end">
                <button type="button" className={BUTTON} onClick={close}>
                  {t('official.cancel')}
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="official-username" className="mb-1 block text-sm font-medium">
                  {t('official.username')}
                </label>
                <input
                  id="official-username"
                  className={FIELD}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </div>
              <div>
                <label htmlFor="official-code" className="mb-1 block text-sm font-medium">
                  {t('official.code')}
                </label>
                <input
                  id="official-code"
                  className={FIELD}
                  value={agentCode}
                  onChange={(event) => setAgentCode(event.target.value)}
                />
              </div>
              {submissionIssue(username, agentCode) === null && (
                <p className="text-sm" data-testid="official-preview">
                  {t('official.preview', {
                    count: record.answers.length,
                    name: record.name,
                    username: username.trim(),
                    code: agentCode.trim(),
                  })}
                </p>
              )}
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={understood}
                  onChange={(event) => setUnderstood(event.target.checked)}
                />
                {t('official.understand')}
              </label>
              {error && (
                <p role="alert" className="text-sm text-error">
                  {t(error)}
                </p>
              )}
              <div className="flex justify-end gap-2">
                <button type="button" className={BUTTON} onClick={close}>
                  {t('official.cancel')}
                </button>
                <button
                  type="button"
                  disabled={!ready}
                  onClick={() => void send()}
                  className={`${BUTTON} border-transparent bg-accent text-on-accent`}
                >
                  {busy ? t('official.sending') : t('official.send')}
                </button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
