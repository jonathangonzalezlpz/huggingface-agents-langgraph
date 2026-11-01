import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { IDLE_BATTERY, type BatteryRequest, type BatteryStatus } from '../../domain/battery';
import { StudioError } from '../../domain/errors';
import type { ExperimentSummary } from '../../domain/battery';
import type { Architecture, ArchitectureSummary } from '../../domain/types';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { BatteryPort, StudioServices } from '../../ports';
import { ExperimentsPage } from './ExperimentsPage';

const base = createMemoryServices();
const [builtinSummary] = await base.architectures.list();
const builtin = await base.architectures.get(builtinSummary?.id ?? '');

function version(number: number, valid: boolean): Architecture {
  return {
    ...builtin,
    id: `alpha-v${number}`,
    architectureId: 'alpha',
    version: number,
    readOnly: false,
    validation: {
      isValid: valid,
      counts: { error: valid ? 0 : 1, warning: 0, info: 0 },
      diagnostics: [],
      availability: {},
    },
  };
}

const good = version(2, true);
const bad = version(1, false);

const status = (over: Partial<BatteryStatus>): BatteryStatus => ({
  ...IDLE_BATTERY,
  ...over,
});

const unfinished: ExperimentSummary = {
  id: 'exp-1',
  status: 'cancelled',
  name: 'Corrida parcial',
  pipelineVersion: '3.1',
  architecture: null,
  completed: 5,
  total: 20,
  createdAt: null,
  averageSeconds: null,
  score: null,
};

function services(over: Partial<StudioServices> = {}): StudioServices {
  const all = [builtin, bad, good];
  return {
    ...base,
    mode: 'live',
    architectures: {
      list: () =>
        Promise.resolve(
          all.map((item): ArchitectureSummary => ({
            id: item.id,
            architectureId: item.architectureId,
            version: item.version,
            parentId: item.parentId,
            contentSha256: item.contentSha256,
            createdAt: item.createdAt,
            readOnly: item.readOnly,
          })),
        ),
      get: (id) => Promise.resolve(all.find((item) => item.id === id) ?? builtin),
      save: base.architectures.save,
    },
    models: { list: () => Promise.resolve([{ provider: 'ollama', modelId: 'llama3' }]) },
    experiments: { list: () => Promise.resolve([unfinished]) },
    batteries: {
      start: () => Promise.resolve(status({ state: 'running', total: 20 })),
      current: () => Promise.resolve(IDLE_BATTERY),
      stop: () => Promise.resolve(status({ state: 'stopping', total: 20 })),
    },
    ...over,
  };
}

function renderPage(current: StudioServices) {
  return render(
    <StudioProviders services={current}>
      <MemoryRouter>
        <ExperimentsPage pollMs={10} />
      </MemoryRouter>
    </StudioProviders>,
  );
}

async function chooseArchitecture(id: string) {
  const select = await screen.findByLabelText('Arquitectura');
  await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1));
  await userEvent.selectOptions(select, id);
}

beforeEach(() => {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('starting a battery', () => {
  it('needs an architecture and only offers versions without errors', async () => {
    renderPage(services());
    const select = await screen.findByLabelText('Arquitectura');
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1));
    expect(within(select).queryByRole('option', { name: /v1/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar batería' })).toBeDisabled();
    await chooseArchitecture('alpha-v2');
    expect(screen.getByRole('button', { name: 'Iniciar batería' })).toBeEnabled();
  });

  it('sends the settings, architecture and question count', async () => {
    const start = vi.fn<BatteryPort['start']>(() =>
      Promise.resolve(status({ state: 'running', total: 3 })),
    );
    renderPage(
      services({
        batteries: { ...services().batteries, start },
      }),
    );
    await chooseArchitecture('alpha-v2');
    const limit = screen.getByLabelText('Preguntas');
    await userEvent.clear(limit);
    await userEvent.type(limit, '3');
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar batería' }));

    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    const request = start.mock.calls[0]?.[0] as Extract<BatteryRequest, { kind: 'new' }>;
    expect(request).toMatchObject({
      kind: 'new',
      architectureId: 'alpha-v2',
      limit: 3,
      settings: { pipelineVersion: '3.1', seed: 42 },
    });
  });

  it('blocks starting while the settings are invalid', async () => {
    renderPage(services());
    await chooseArchitecture('alpha-v2');
    await userEvent.click(screen.getByText('Ajustes avanzados'));
    const solution = screen.getByLabelText('Tokens de solución');
    await userEvent.clear(solution);
    await userEvent.type(solution, '10');
    expect(screen.getByRole('alert')).toHaveTextContent(/al menos 128 tokens/);
    expect(screen.getByRole('button', { name: 'Iniciar batería' })).toBeDisabled();
  });

  it('does not allow more than 20 questions', async () => {
    renderPage(services());
    await chooseArchitecture('alpha-v2');
    const limit = screen.getByLabelText('Preguntas');
    await userEvent.clear(limit);
    await userEvent.type(limit, '21');
    expect(screen.getByRole('button', { name: 'Iniciar batería' })).toBeDisabled();
  });

  it('says so when another battery is already running', async () => {
    const start = () => Promise.reject(new StudioError('http', 'busy', 409));
    renderPage(services({ batteries: { ...services().batteries, start } }));
    await chooseArchitecture('alpha-v2');
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar batería' }));
    expect(await screen.findByText(/Ya hay una batería en curso/)).toBeVisible();
  });
});

describe('following a battery', () => {
  it('shows progress as the server reports it, and refreshes the list when it ends', async () => {
    const steps = [
      status({ state: 'running', name: 'Studio', completed: 4, total: 20, experimentId: 'e' }),
      status({ state: 'running', name: 'Studio', completed: 12, total: 20, experimentId: 'e' }),
      status({ state: 'completed', name: 'Studio', completed: 20, total: 20, experimentId: 'e' }),
    ];
    let polls = 0;
    const list = vi.fn(() => Promise.resolve([unfinished]));
    renderPage(
      services({
        experiments: { list },
        batteries: {
          ...services().batteries,
          current: () =>
            Promise.resolve(steps[Math.min(polls++, steps.length - 1)] as BatteryStatus),
        },
      }),
    );
    expect(await screen.findByText('4 de 20 preguntas', { exact: false })).toBeVisible();
    expect(await screen.findByText('12 de 20 preguntas', { exact: false })).toBeVisible();
    expect(await screen.findByText('Completada')).toBeVisible();
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('progressbar', { name: 'Progreso de la batería' })).toHaveValue(20);
  });

  it('picks up a battery that was already running when the page opened', async () => {
    renderPage(
      services({
        batteries: {
          ...services().batteries,
          current: () =>
            Promise.resolve(status({ state: 'running', name: 'Previa', completed: 2, total: 20 })),
        },
      }),
    );
    expect(await screen.findByText('Previa')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Detener' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Iniciar batería' })).toBeDisabled();
  });

  it('stops after the current question and explains it', async () => {
    let server = status({ state: 'running', name: 'Previa', completed: 2, total: 20 });
    const stop = vi.fn<BatteryPort['stop']>(() => {
      server = { ...server, state: 'stopping' };
      return Promise.resolve(server);
    });
    renderPage(
      services({
        batteries: { ...services().batteries, current: () => Promise.resolve(server), stop },
      }),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Detener' }));
    expect(stop).toHaveBeenCalledOnce();
    expect(await screen.findByText(/no puede interrumpirla/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Detener' })).toBeDisabled();
  });

  it('shows why a battery failed', async () => {
    renderPage(
      services({
        batteries: {
          ...services().batteries,
          current: () =>
            Promise.resolve(status({ state: 'failed', name: 'Rota', error: 'code changed' })),
        },
      }),
    );
    expect(await screen.findByText('code changed')).toBeVisible();
    expect(screen.getByText('Fallida')).toBeVisible();
  });
});

describe('unfinished experiments', () => {
  it('lists them and resumes one by id', async () => {
    const start = vi.fn<BatteryPort['start']>(() =>
      Promise.resolve(status({ state: 'running', total: 20 })),
    );
    renderPage(services({ batteries: { ...services().batteries, start } }));
    await userEvent.click(await screen.findByRole('button', { name: 'Reanudar Corrida parcial' }));
    expect(start).toHaveBeenCalledWith({ kind: 'resume', experimentId: 'exp-1' });
  });

  it('does not list finished experiments', async () => {
    renderPage(
      services({
        experiments: {
          list: () => Promise.resolve([{ ...unfinished, status: 'completed', completed: 20 }]),
        },
      }),
    );
    expect(await screen.findByText('No hay experimentos sin terminar.')).toBeVisible();
  });

  it('cannot resume while another battery is running', async () => {
    renderPage(
      services({
        batteries: {
          ...services().batteries,
          current: () => Promise.resolve(status({ state: 'running', name: 'X', total: 20 })),
        },
      }),
    );
    expect(await screen.findByRole('button', { name: 'Reanudar Corrida parcial' })).toBeDisabled();
  });
});

describe('demo mode', () => {
  it('explains that batteries need the backend and cannot start', async () => {
    renderPage({ ...services(), mode: 'demo' });
    expect(await screen.findByText(/modo demostración/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Iniciar batería' })).toBeDisabled();
  });
});

describe('accessibility', () => {
  it('has no detectable violations', async () => {
    const { container } = renderPage(
      services({
        batteries: {
          ...services().batteries,
          current: () =>
            Promise.resolve(status({ state: 'running', name: 'X', completed: 1, total: 20 })),
        },
      }),
    );
    await screen.findByText('X');
    const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
