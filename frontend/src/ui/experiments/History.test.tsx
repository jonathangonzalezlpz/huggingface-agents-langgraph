import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { StudioError } from '../../domain/errors';
import type {
  Comparison,
  ExperimentAnswer,
  ExperimentRecord,
  OfficialSubmission,
} from '../../domain/history';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { ExperimentPort, StudioServices } from '../../ports';
import { ExperimentDetailPage } from './ExperimentDetailPage';
import { ExperimentsLayout } from './ExperimentsLayout';
import { HistoryPage } from './HistoryPage';

const base = createMemoryServices();

const answer = (n: number, over: Partial<ExperimentAnswer> = {}): ExperimentAnswer => ({
  taskId: `t${n}`,
  question: `Pregunta ${n}`,
  fileName: '',
  answer: `resp ${n}`,
  error: '',
  route: 'direct',
  durationSeconds: 2.5,
  runId: `run-${n}`,
  locallyCorrect: null,
  ...over,
});

function record(id: string, over: Partial<ExperimentRecord> = {}): ExperimentRecord {
  return {
    id,
    status: 'completed',
    name: `Exp ${id}`,
    pipelineVersion: '3.1',
    architecture: null,
    completed: 20,
    total: 20,
    createdAt: '2026-11-01T10:00:00Z',
    averageSeconds: 50,
    answers: Array.from({ length: 20 }, (_, n) => answer(n)),
    localScore: null,
    officialScore: null,
    ...over,
  };
}

const alpha = record('alpha', {
  name: 'Alpha',
  createdAt: '2026-10-01T10:00:00Z',
  localScore: { percent: 45, correct: 9, attempted: 20 },
  averageSeconds: 45,
});
const beta = record('beta', {
  name: 'Beta',
  createdAt: '2026-11-02T10:00:00Z',
  localScore: { percent: 50, correct: 10, attempted: 20 },
  averageSeconds: 60,
  architecture: 'builtin:gaia_v31',
});
const gamma = record('gamma', {
  name: 'Gamma',
  status: 'cancelled',
  answers: [answer(1)],
  completed: 1,
});

const comparison: Comparison = {
  baseGroup: 'g1',
  experiments: [
    {
      id: 'alpha',
      name: 'Alpha',
      status: 'completed',
      group: 'g1',
      metrics: {
        answered: 20,
        correct: 9,
        accuracy: 0.45,
        meanSeconds: 45,
        medianSeconds: 40,
        p95Seconds: 80,
        technicalErrors: 2,
        truncatedCalls: 1,
      },
    },
    {
      id: 'beta',
      name: 'Beta',
      status: 'completed',
      group: 'g2',
      metrics: {
        answered: 20,
        correct: 10,
        accuracy: 0.5,
        meanSeconds: 60,
        medianSeconds: 55,
        p95Seconds: 90,
        technicalErrors: 0,
        truncatedCalls: 0,
      },
    },
  ],
  groups: [
    {
      key: 'g1',
      experimentIds: ['alpha'],
      runs: 1,
      accuracy: { min: 0.45, max: 0.45, mean: 0.45 },
      meanSeconds: { min: 45, max: 45, mean: 45 },
      versusBase: null,
    },
    {
      key: 'g2',
      experimentIds: ['beta'],
      runs: 1,
      accuracy: { min: 0.5, max: 0.5, mean: 0.5 },
      meanSeconds: { min: 60, max: 60, mean: 60 },
      versusBase: {
        gained: 3,
        lost: 2,
        unchanged: 15,
        unknown: 0,
        accuracyDelta: 0.05,
        assessment: 'not_assessable',
        meanSecondsDelta: 15,
      },
    },
  ],
  comparability: {
    sameTaskSet: true,
    sameCode: null,
    sameArchitecture: true,
    configDifferences: ['seed'],
    warnings: ['Code identity is unknown for some experiments.', 'Something new from the backend.'],
  },
  tasks: [
    {
      taskId: 't0',
      outcomes: {
        alpha: { correct: true, route: 'direct', seconds: 3, error: false, versusBase: null },
        beta: { correct: false, route: 'direct', seconds: 4, error: true, versusBase: 'lost' },
      },
    },
  ],
};

function experimentsPort(over: Partial<ExperimentPort> = {}): ExperimentPort {
  return {
    list: () => Promise.resolve([alpha, beta, gamma]),
    remove: () => Promise.resolve(),
    evaluate: () => Promise.resolve({ percent: 40, correct: 8, attempted: 20 }),
    submitOfficial: () =>
      Promise.resolve({ score: { percent: 45, correct: 9, attempted: 20 }, saved: true }),
    compare: () => Promise.resolve(comparison),
    ...over,
  };
}

function services(over: Partial<ExperimentPort> = {}): StudioServices {
  return { ...base, mode: 'live', experiments: experimentsPort(over) };
}

function renderAt(path: string, current: StudioServices) {
  return render(
    <StudioProviders services={current}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/experiments" element={<ExperimentsLayout />}>
            <Route path="history" element={<HistoryPage />} />
            <Route path=":id" element={<ExperimentDetailPage />} />
          </Route>
          <Route path="/runs/:id" element={<p>vista de ejecución</p>} />
        </Routes>
      </MemoryRouter>
    </StudioProviders>,
  );
}

const rows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1);

beforeEach(() => {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('history list', () => {
  it('shows every experiment with its score and status, newest first', async () => {
    renderAt('/experiments/history', services());
    await screen.findByRole('link', { name: 'Alpha' });
    expect(rows().map((row) => within(row).getByRole('link').textContent)).toEqual([
      'Beta',
      'Gamma',
      'Alpha',
    ]);
    expect(within(rows()[0] as HTMLElement).getByText('50.0 % · 10/20')).toBeVisible();
    expect(within(rows()[0] as HTMLElement).getByText('Integrada')).toBeVisible();
    expect(within(rows()[1] as HTMLElement).getByText('Detenido')).toBeVisible();
    expect(within(rows()[1] as HTMLElement).getByText('Sin puntuar')).toBeVisible();
  });

  it('filters by text and re-sorts by score', async () => {
    renderAt('/experiments/history', services());
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'score');
    expect(within(rows()[0] as HTMLElement).getByRole('link')).toHaveTextContent('Beta');
    await userEvent.type(screen.getByLabelText('Buscar experimentos'), 'gam');
    expect(rows()).toHaveLength(1);
    await userEvent.clear(screen.getByLabelText('Buscar experimentos'));
    await userEvent.type(screen.getByLabelText('Buscar experimentos'), 'zzz');
    expect(screen.getByText('Ningún experimento coincide.')).toBeVisible();
  });

  it('explains when there is nothing stored', async () => {
    renderAt('/experiments/history', services({ list: () => Promise.resolve([]) }));
    expect(await screen.findByText('Aún no hay experimentos guardados.')).toBeVisible();
  });

  it('offers a way back from a failed load', async () => {
    renderAt(
      '/experiments/history',
      services({ list: () => Promise.reject(new StudioError('network', 'down')) }),
    );
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeVisible();
  });
});

describe('comparing', () => {
  it('needs two experiments, and sends the chosen ids and base', async () => {
    const compare = vi.fn<ExperimentPort['compare']>(() => Promise.resolve(comparison));
    renderAt('/experiments/history', services({ compare }));
    await screen.findByRole('link', { name: 'Alpha' });
    const button = screen.getByRole('button', { name: 'Comparar' });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Alpha' }));
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Beta' }));
    expect(screen.getByRole('status')).toHaveTextContent('2 seleccionados');
    await userEvent.selectOptions(screen.getByLabelText('Base de la comparación'), 'beta');
    await userEvent.click(button);

    await screen.findByRole('heading', { name: 'Comparación' });
    expect(compare).toHaveBeenCalledWith({ ids: ['alpha', 'beta'], base: 'beta' });
  });

  it('shows groups, comparability, translated warnings and per-question outcomes', async () => {
    renderAt('/experiments/history', services());
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Alpha' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Beta' }));
    await userEvent.click(screen.getByRole('button', { name: 'Comparar' }));

    const groups = within(await screen.findByRole('region', { name: 'Grupos' }));
    expect(groups.getByText(/Ganadas: 3 · Perdidas: 2 · Sin cambio: 15/)).toBeVisible();
    expect(groups.getByText('No evaluable: hace falta repetir')).toBeVisible();
    const comparability = within(screen.getByRole('region', { name: 'Comparabilidad' }));
    expect(
      comparability.getByText('Se desconoce el código de algunos experimentos.'),
    ).toBeVisible();
    expect(comparability.getByText('Something new from the backend.')).toBeVisible();
    expect(comparability.getByText(/Ajustes distintos: seed/)).toBeVisible();
    const tasks = within(screen.getByRole('region', { name: 'Pregunta por pregunta' }));
    expect(tasks.getByText('Fallo · con error · perdida')).toBeVisible();
    expect(tasks.getByText('Pregunta 0')).toBeVisible();
  });

  it('shows a failed comparison with a retry', async () => {
    renderAt(
      '/experiments/history',
      services({ compare: () => Promise.reject(new StudioError('http', 'x', 400)) }),
    );
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Alpha' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Beta' }));
    await userEvent.click(screen.getByRole('button', { name: 'Comparar' }));
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeVisible();
  });
});

describe('deleting', () => {
  it('asks first, and removes only after confirmation', async () => {
    const remove = vi.fn<ExperimentPort['remove']>(() => Promise.resolve());
    const list = vi
      .fn<ExperimentPort['list']>()
      .mockResolvedValueOnce([alpha, beta])
      .mockResolvedValue([beta]);
    renderAt('/experiments/history', services({ remove, list }));
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar: Alpha' }));
    const dialog = within(await screen.findByRole('dialog', { name: 'Eliminar experimento' }));
    expect(dialog.getByText(/«Alpha»/)).toBeVisible();
    expect(remove).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Eliminar' }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith('alpha'));
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'Alpha' })).not.toBeInTheDocument(),
    );
  });

  it('can be cancelled without touching anything', async () => {
    const remove = vi.fn<ExperimentPort['remove']>(() => Promise.resolve());
    renderAt('/experiments/history', services({ remove }));
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar: Alpha' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar' }));
    expect(remove).not.toHaveBeenCalled();
  });

  it('says so when the server refuses', async () => {
    const remove = () => Promise.reject(new StudioError('http', 'x', 400));
    renderAt('/experiments/history', services({ remove }));
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar: Alpha' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Eliminar' }));
    expect(await screen.findByText('No se pudo eliminar el experimento.')).toBeVisible();
  });
});

describe('experiment detail', () => {
  it('lists each answer with its result and a link to its path', async () => {
    const scored = record('alpha', {
      name: 'Alpha',
      answers: [
        answer(1, { locallyCorrect: true }),
        answer(2, { locallyCorrect: false, error: 'boom', runId: null }),
      ],
    });
    renderAt('/experiments/alpha', services({ list: () => Promise.resolve([scored]) }));
    const table = within(await screen.findByRole('table'));
    expect(table.getByText('Acierto')).toBeVisible();
    expect(table.getByText('Fallo')).toBeVisible();
    expect(table.getByText('Error: boom')).toBeVisible();
    expect(table.getByRole('link', { name: 'Ver recorrido' })).toHaveAttribute(
      'href',
      '/runs/run-1',
    );
    expect(table.getByText('Sin traza')).toBeVisible();
  });

  it('links the attachment of a question that has one', async () => {
    const withFile = record('f', {
      name: 'F',
      answers: [answer(1, { fileName: 'data.xlsx' }), answer(2)],
    });
    renderAt('/experiments/f', services({ list: () => Promise.resolve([withFile]) }));
    const table = within(await screen.findByRole('table'));
    expect(table.getAllByRole('link', { name: 'Descargar adjunto' })).toHaveLength(1);
    expect(table.getByRole('link', { name: 'Descargar adjunto' })).toHaveAttribute(
      'href',
      '/api/files/t1',
    );
  });

  it('says when the experiment does not exist', async () => {
    renderAt('/experiments/nope', services());
    expect(await screen.findByText('No existe ese experimento.')).toBeVisible();
  });

  it('scores locally and refreshes', async () => {
    const evaluate = vi.fn<ExperimentPort['evaluate']>(() =>
      Promise.resolve({ percent: 40, correct: 8, attempted: 20 }),
    );
    const list = vi
      .fn<ExperimentPort['list']>()
      .mockResolvedValueOnce([record('x', { name: 'X' })])
      .mockResolvedValue([
        record('x', { name: 'X', localScore: { percent: 40, correct: 8, attempted: 20 } }),
      ]);
    renderAt('/experiments/x', services({ evaluate, list }));
    await userEvent.click(await screen.findByRole('button', { name: 'Puntuar localmente' }));
    expect(evaluate).toHaveBeenCalledWith('x');
    expect(await screen.findByText('40.0 % · 8/20')).toBeVisible();
  });

  it('cannot score an incomplete experiment', async () => {
    renderAt('/experiments/gamma', services());
    expect(await screen.findByRole('button', { name: 'Puntuar localmente' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Enviar al evaluador oficial…' })).toBeDisabled();
    expect(screen.getByText('Necesita las 20 respuestas.')).toBeVisible();
  });

  it('explains when GAIA validation cannot be loaded', async () => {
    const evaluate = () => Promise.reject(new StudioError('http', 'x', 503));
    renderAt('/experiments/alpha', services({ evaluate }));
    await userEvent.click(await screen.findByRole('button', { name: 'Puntuar localmente' }));
    expect(await screen.findByText(/No se pudo cargar GAIA validation/)).toBeVisible();
  });
});

describe('official submission', () => {
  async function openDialog(over: Partial<ExperimentPort> = {}) {
    renderAt('/experiments/alpha', services(over));
    await userEvent.click(
      await screen.findByRole('button', { name: 'Enviar al evaluador oficial…' }),
    );
    return within(await screen.findByRole('dialog', { name: 'Enviar al evaluador oficial' }));
  }

  it('warns that it is public and sends nothing until everything is confirmed', async () => {
    const submitOfficial = vi.fn<ExperimentPort['submitOfficial']>(() =>
      Promise.resolve({ score: { percent: 45, correct: 9, attempted: 20 }, saved: true }),
    );
    const dialog = await openDialog({ submitOfficial });
    expect(dialog.getByText(/servicio externo con clasificación pública/)).toBeVisible();
    const send = dialog.getByRole('button', { name: 'Enviar' });
    expect(send).toBeDisabled();

    await userEvent.type(dialog.getByLabelText('Usuario de Hugging Face'), 'someone');
    expect(send).toBeDisabled();
    await userEvent.type(dialog.getByLabelText('Enlace al código del agente'), 'https://code');
    expect(dialog.getByTestId('official-preview')).toHaveTextContent(
      'Se enviarán 20 respuestas del experimento «Alpha» con el usuario someone y el enlace https://code.',
    );
    expect(send).toBeDisabled();
    await userEvent.click(dialog.getByRole('checkbox'));
    expect(send).toBeEnabled();
    expect(submitOfficial).not.toHaveBeenCalled();

    await userEvent.click(send);
    expect(submitOfficial).toHaveBeenCalledWith({
      experimentId: 'alpha',
      username: 'someone',
      agentCode: 'https://code',
    } satisfies OfficialSubmission);
    expect(await dialog.findByText('Enviado: 45.0 % · 9/20.')).toBeVisible();
  });

  it('refreshes the experiment once the dialog is closed after a successful send', async () => {
    const list = vi.fn<ExperimentPort['list']>(() => Promise.resolve([alpha]));
    const dialog = await openDialog({ list });
    await userEvent.type(dialog.getByLabelText('Usuario de Hugging Face'), 'u');
    await userEvent.type(dialog.getByLabelText('Enlace al código del agente'), 'c');
    await userEvent.click(dialog.getByRole('checkbox'));
    await userEvent.click(dialog.getByRole('button', { name: 'Enviar' }));
    await dialog.findByText(/Enviado/);
    expect(list).toHaveBeenCalledTimes(1);
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it('can be cancelled without sending', async () => {
    const submitOfficial = vi.fn<ExperimentPort['submitOfficial']>();
    const dialog = await openDialog({ submitOfficial });
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(submitOfficial).not.toHaveBeenCalled();
  });

  it('says nothing was sent when the evaluator is unreachable', async () => {
    const dialog = await openDialog({
      submitOfficial: () => Promise.reject(new StudioError('http', 'x', 502)),
    });
    await userEvent.type(dialog.getByLabelText('Usuario de Hugging Face'), 'u');
    await userEvent.type(dialog.getByLabelText('Enlace al código del agente'), 'c');
    await userEvent.click(dialog.getByRole('checkbox'));
    await userEvent.click(dialog.getByRole('button', { name: 'Enviar' }));
    expect(await dialog.findByText(/No se ha enviado nada/)).toBeVisible();
  });

  it('warns when the verdict arrived but could not be stored', async () => {
    const dialog = await openDialog({
      submitOfficial: () =>
        Promise.resolve({ score: { percent: 5, correct: 1, attempted: 20 }, saved: false }),
    });
    await userEvent.type(dialog.getByLabelText('Usuario de Hugging Face'), 'u');
    await userEvent.type(dialog.getByLabelText('Enlace al código del agente'), 'c');
    await userEvent.click(dialog.getByRole('checkbox'));
    await userEvent.click(dialog.getByRole('button', { name: 'Enviar' }));
    expect(await dialog.findByText(/no se pudo guardar en el experimento/)).toBeVisible();
  });

  it('is not offered again once the experiment has an official score', async () => {
    const sent = record('done', {
      name: 'Done',
      officialScore: { percent: 45, correct: 9, attempted: 20 },
    });
    renderAt('/experiments/done', services({ list: () => Promise.resolve([sent]) }));
    expect(await screen.findByRole('button', { name: 'Ya enviado' })).toBeDisabled();
  });
});

describe('accessibility', () => {
  it('has no detectable violations on the list, the comparison and the detail', async () => {
    const { container } = renderAt('/experiments/history', services());
    await screen.findByRole('link', { name: 'Alpha' });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Alpha' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Elegir Beta' }));
    await userEvent.click(screen.getByRole('button', { name: 'Comparar' }));
    await screen.findByRole('region', { name: 'Grupos' });
    const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });

  it('has no detectable violations on the detail page', async () => {
    const { container } = renderAt('/experiments/alpha', services());
    await screen.findByRole('table');
    const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
