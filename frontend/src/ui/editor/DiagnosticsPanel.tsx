import type { ValidationReport } from '../../domain/types';
import { isMessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { StatusBadge, type Tone } from '../components/StatusBadge';

export type ValidationView =
  | { status: 'idle' }
  | { status: 'running' }
  | { status: 'done'; report: ValidationReport }
  | { status: 'unavailable' }
  | { status: 'failed' };

const TONE: Record<'error' | 'warning' | 'info', Tone> = {
  error: 'error',
  warning: 'warning',
  info: 'info',
};

export function DiagnosticsPanel({
  view,
  stale,
  onGoto,
}: {
  view: ValidationView;
  stale: boolean;
  onGoto: (nodeId: string) => void;
}) {
  const { t, tp } = useI18n();

  return (
    <section aria-labelledby="diagnostics-title" className="p-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 id="diagnostics-title" className="text-sm font-semibold">
          {t('editor.diagnostics')}
        </h2>
        {view.status === 'done' && (
          <p className="text-xs text-fg-muted">
            {tp('diagnostics.errors', view.report.counts.error)}
            {' · '}
            {tp('diagnostics.warnings', view.report.counts.warning)}
            {' · '}
            {tp('diagnostics.infos', view.report.counts.info)}
          </p>
        )}
      </div>

      <div role="status" aria-live="polite">
        {view.status === 'idle' && (
          <p className="mt-2 text-sm text-fg-muted">{t('editor.diagnostics.idle')}</p>
        )}
        {view.status === 'running' && (
          <p className="mt-2 text-sm text-fg-muted">{t('editor.diagnostics.running')}</p>
        )}
        {view.status === 'unavailable' && (
          <p className="mt-2 text-sm text-warning">{t('editor.diagnostics.unavailable')}</p>
        )}
        {view.status === 'failed' && (
          <p className="mt-2 text-sm text-error">{t('editor.diagnostics.failed')}</p>
        )}
        {stale && <p className="mt-2 text-sm text-warning">{t('editor.diagnostics.stale')}</p>}
      </div>

      {view.status === 'done' && view.report.diagnostics.length === 0 && (
        <p className="mt-2 text-sm text-fg-muted">{t('editor.diagnostics.clean')}</p>
      )}

      {view.status === 'done' && view.report.diagnostics.length > 0 && (
        <ul className="mt-3 max-h-48 space-y-2 overflow-y-auto">
          {view.report.diagnostics.map((item, index) => {
            const key = `diagnostic.${item.code}`;
            const node = item.nodeId ?? item.edgeSource;
            return (
              <li
                key={`${item.code}-${node ?? ''}-${index}`}
                className="rounded-lg border border-line bg-surface p-2.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge tone={TONE[item.severity]}>{item.code}</StatusBadge>
                  {node && (
                    <button
                      type="button"
                      onClick={() => onGoto(node)}
                      aria-label={t('editor.diagnostics.goto', { node })}
                      className="font-mono text-xs text-accent-fg underline underline-offset-2"
                    >
                      {node}
                    </button>
                  )}
                </div>
                <p className="mt-1 text-sm">{isMessageKey(key) ? t(key) : item.message}</p>
                <details className="mt-1 text-xs text-fg-muted">
                  <summary className="cursor-pointer">{t('editor.diagnostics.technical')}</summary>
                  <p className="mt-1 font-mono">{item.message}</p>
                </details>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
