import { Navigate, Route, Routes } from 'react-router-dom';

import { BuilderPage } from '../ui/pages/BuilderPage';
import { ExperimentsPage, NotFoundPage, RunsPage, SystemPage } from '../ui/pages/OtherPages';
import { AppShell } from '../ui/shell/AppShell';

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/builder" replace />} />
        <Route path="builder" element={<BuilderPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="experiments" element={<ExperimentsPage />} />
        <Route path="system" element={<SystemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
