import { ArrowLeft } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { StudioError } from '../../domain/errors';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { useAsyncData } from '../hooks/useAsyncData';
import { TabBar } from '../observability/TabBar';
import { TraceView } from '../observability/TraceView';
import { useServices } from '../services';
import { RunResult } from './RunResult';

/** A past run opened by its id, for example from an experiment's answer. */
export function RunViewPage() {
  const { t } = useI18n();
  const { runs } = useServices();
  const { id = '' } = useParams();
  const state = useAsyncData(useCallback(() => runs.get(id), [runs, id]));
  const [view, setView] = useState<'path' | 'trace'>('path');

  return (
    <>
      <PageHeader title={t('runs.title')} description={t('runs.description')} />
      <Link
        to="/runs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-accent-fg underline underline-offset-2"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        {t('runs.view.back')}
      </Link>
      {state.status === 'loading' && <p className="text-fg-muted">{t('common.loading')}</p>}
      {state.status === 'error' &&
        (state.error instanceof StudioError && state.error.status === 404 ? (
          <p>{t('runs.view.notFound')}</p>
        ) : (
          <ErrorNotice error={state.error} onRetry={state.reload} />
        ))}
      {state.status === 'success' && (
        <>
          <TabBar
            label={t('obs.tab.label')}
            value={view}
            onChange={setView}
            tabs={[
              { id: 'path', label: t('obs.tab.path') },
              { id: 'trace', label: t('obs.tab.trace') },
            ]}
          />
          <div role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
            {view === 'path' ? <RunResult record={state.data} /> : <TraceView runId={id} />}
          </div>
        </>
      )}
    </>
  );
}
