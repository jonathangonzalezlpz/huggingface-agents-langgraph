import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { StudioError } from '../../domain/errors';
import type { RunRecord } from '../../domain/run';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { RunPort, StudioServices } from '../../ports';
import { installReactFlowMocks } from '../../test/reactFlow';
import { stubMatchMedia } from '../../test/setup';
import { RunViewPage } from './RunViewPage';

const base = createMemoryServices();

const record: RunRecord = {
  id: 'run-1',
  status: 'completed',
  durationSeconds: 3,
  steps: [{ node: 'preprocessing', durationSeconds: 1, error: null, updatedFields: ['question'] }],
  architecture: null,
  question: 'q',
  answer: '391',
  route: 'direct',
  error: null,
  modelId: null,
};

function renderRun(get: RunPort['get']) {
  const services: StudioServices = { ...base, mode: 'live', runs: { run: base.runs.run, get } };
  return render(
    <StudioProviders services={services}>
      <MemoryRouter initialEntries={['/runs/run-1']}>
        <Routes>
          <Route path="/runs/:id" element={<RunViewPage />} />
        </Routes>
      </MemoryRouter>
    </StudioProviders>,
  );
}

beforeEach(() => {
  installReactFlowMocks();
  stubMatchMedia(false, true);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('opening a past run', () => {
  it('shows its result', async () => {
    renderRun(() => Promise.resolve(record));
    expect(await screen.findByText('391')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Volver a Ejecuciones' })).toHaveAttribute(
      'href',
      '/runs',
    );
  });

  it('says so when the run does not exist', async () => {
    renderRun(() => Promise.reject(new StudioError('http', 'x', 404)));
    expect(await screen.findByText('No existe esa ejecución.')).toBeVisible();
  });

  it('offers a retry when loading fails', async () => {
    renderRun(() => Promise.reject(new StudioError('network', 'down')));
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeVisible();
  });
});
