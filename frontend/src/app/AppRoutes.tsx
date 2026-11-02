import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { useI18n } from '../i18n/I18nProvider';
import { BuilderPage } from '../ui/pages/BuilderPage';
import { NotFoundPage, SystemPage } from '../ui/pages/OtherPages';
import { AppShell } from '../ui/shell/AppShell';

// The editor brings the graph canvas library, so it loads only when it is opened.
const ArchitectureEditorPage = lazy(() =>
  import('../ui/editor/EditorPage').then((m) => ({ default: m.ArchitectureEditorPage })),
);
const DraftEditorPage = lazy(() =>
  import('../ui/editor/EditorPage').then((m) => ({ default: m.DraftEditorPage })),
);

const ExperimentsLayout = lazy(() =>
  import('../ui/experiments/ExperimentsLayout').then((m) => ({ default: m.ExperimentsLayout })),
);
const ExperimentsPage = lazy(() =>
  import('../ui/experiments/ExperimentsPage').then((m) => ({ default: m.ExperimentsPage })),
);
const HistoryPage = lazy(() =>
  import('../ui/experiments/HistoryPage').then((m) => ({ default: m.HistoryPage })),
);
const ExperimentDetailPage = lazy(() =>
  import('../ui/experiments/ExperimentDetailPage').then((m) => ({
    default: m.ExperimentDetailPage,
  })),
);
const RunViewPage = lazy(() =>
  import('../ui/run/RunViewPage').then((m) => ({ default: m.RunViewPage })),
);
const RunsPage = lazy(() => import('../ui/run/RunsPage').then((m) => ({ default: m.RunsPage })));

function Loading() {
  const { t } = useI18n();
  return <p className="p-8 text-fg-muted">{t('common.loading')}</p>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/builder" replace />} />
        <Route path="builder" element={<BuilderPage />} />
        <Route
          path="builder/architecture/:id"
          element={
            <Suspense fallback={<Loading />}>
              <ArchitectureEditorPage />
            </Suspense>
          }
        />
        <Route
          path="builder/draft/:id"
          element={
            <Suspense fallback={<Loading />}>
              <DraftEditorPage />
            </Suspense>
          }
        />
        <Route
          path="runs"
          element={
            <Suspense fallback={<Loading />}>
              <RunsPage />
            </Suspense>
          }
        />
        <Route
          path="runs/:id"
          element={
            <Suspense fallback={<Loading />}>
              <RunViewPage />
            </Suspense>
          }
        />
        <Route
          path="experiments"
          element={
            <Suspense fallback={<Loading />}>
              <ExperimentsLayout />
            </Suspense>
          }
        >
          <Route
            index
            element={
              <Suspense fallback={<Loading />}>
                <ExperimentsPage />
              </Suspense>
            }
          />
          <Route
            path="history"
            element={
              <Suspense fallback={<Loading />}>
                <HistoryPage />
              </Suspense>
            }
          />
          <Route
            path=":id"
            element={
              <Suspense fallback={<Loading />}>
                <ExperimentDetailPage />
              </Suspense>
            }
          />
        </Route>
        <Route path="system" element={<SystemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
