import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { RunResult } from './RunResult';
import type { RunState } from './useRunner';

/** What the page shows below the form for each state of the run. */
export function RunOutcome({ state, onRetry }: { state: RunState; onRetry: () => void }) {
  const { t } = useI18n();
  switch (state.status) {
    case 'idle':
      return <p className="text-fg-muted">{t('runs.empty')}</p>;
    case 'stopped':
      return (
        <p role="status" className="text-fg-muted">
          {t('runs.stopped')}
        </p>
      );
    case 'failed':
      return <ErrorNotice error={state.error} onRetry={onRetry} />;
    case 'done':
      return <RunResult record={state.record} />;
    case 'running':
      return null;
  }
}
