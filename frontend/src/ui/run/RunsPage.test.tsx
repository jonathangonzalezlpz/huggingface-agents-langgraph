import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { StudioError } from '../../domain/errors';
import type { GaiaQuestion, RunRecord } from '../../domain/run';
import type { Architecture, ArchitectureSummary } from '../../domain/types';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { RunPort, StudioServices } from '../../ports';
import { installReactFlowMocks } from '../../test/reactFlow';
import { stubMatchMedia } from '../../test/setup';
import { RunsPage } from './RunsPage';

const base = createMemoryServices();
const [builtinSummary] = await base.architectures.list();
const builtin = await base.architectures.get(builtinSummary?.id ?? '');

function version(number: number, valid: boolean): Architecture {
  return {
    id: `alpha-v${number}`,
    architectureId: 'alpha',
    version: number,
    parentId: null,
    contentSha256: `${number}`.repeat(64),
    createdAt: '2026-11-01T10:00:00Z',
    readOnly: false,
    definition: {
      schemaVersion: '4.0',
      architectureId: 'alpha',
      stateType: 'AgentState',
      initialNode: 'preprocessing',
      nodes: [
        { id: 'preprocessing', implementationId: 'preprocessing', description: '' },
        { id: 'reasoning', implementationId: 'reasoning', description: '' },
      ],
      edges: [
        { type: 'direct', source: 'preprocessing', target: 'reasoning' },
        { type: 'direct', source: 'reasoning', target: '__end__' },
      ],
    },
    validation: {
      isValid: valid,
      counts: { error: valid ? 0 : 1, warning: 0, info: 0 },
      diagnostics: [],
      availability: {},
    },
  };
}

const bad = version(1, false);
const good = version(2, true);

function record(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    id: 'run-1',
    status: 'completed',
    durationSeconds: 3.2,
    steps: [
      { node: 'preprocessing', durationSeconds: 0.4, error: null, updatedFields: ['question'] },
      { node: 'reasoning', durationSeconds: 2.8, error: null, updatedFields: ['answer'] },
    ],
    architecture: { engine: 'declarative', id: good.id, version: 2, contentSha256: 'b'.repeat(64) },
    question: 'q',
    answer: '391',
    route: 'direct',
    error: null,
    modelId: 'qwen',
    ...overrides,
  };
}

const gaiaQuestion: GaiaQuestion = {
  taskId: 'task-9',
  question: 'What is on the attached sheet?',
  fileName: 'sheet.xlsx',
  level: '1',
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
      get: (id) => {
        const found = all.find((item) => item.id === id);
        return found ? Promise.resolve(found) : Promise.reject(new Error('missing'));
      },
      save: base.architectures.save,
    },
    models: { list: () => Promise.resolve([{ provider: 'ollama', modelId: 'llama3' }]) },
    questions: { list: () => Promise.resolve([gaiaQuestion]) },
    runs: { run: () => Promise.resolve(record()), get: () => Promise.resolve(record()) },
    ...over,
  };
}

function renderRuns(current: StudioServices, path = '/runs') {
  return render(
    <StudioProviders services={current}>
      <MemoryRouter initialEntries={[path]}>
        <RunsPage />
      </MemoryRouter>
    </StudioProviders>,
  );
}

async function choose(version: string) {
  const select = await screen.findByLabelText('Arquitectura');
  await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1));
  await userEvent.selectOptions(select, version);
}

beforeEach(() => {
  installReactFlowMocks();
  stubMatchMedia(false, true);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('choosing what to run', () => {
  it('explains why a version with errors cannot run', async () => {
    renderRuns(services());
    await choose('alpha-v1');
    await userEvent.type(screen.getByLabelText('Pregunta'), 'hola');
    expect(screen.getByRole('alert')).toHaveTextContent(/errores de validación/);
    expect(screen.getByRole('button', { name: 'Ejecutar' })).toBeDisabled();
  });

  it('preselects the version named in the address', async () => {
    renderRuns(services(), '/runs?architecture=alpha-v2');
    await waitFor(() => expect(screen.getByLabelText('Arquitectura')).toHaveValue('alpha-v2'));
  });

  it('needs a question before it can run', async () => {
    renderRuns(services());
    await choose('alpha-v2');
    expect(screen.getByRole('button', { name: 'Ejecutar' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '¿Cuánto es 17 por 23?' }));
    expect(screen.getByRole('button', { name: 'Ejecutar' })).toBeEnabled();
  });
});

describe('running', () => {
  it('sends the request and shows the answer and the steps', async () => {
    const run = vi.fn<RunPort['run']>(() => Promise.resolve(record()));
    renderRuns(services({ runs: { run, get: () => Promise.resolve(record()) } }));
    await choose('alpha-v2');
    await userEvent.selectOptions(screen.getByLabelText('Modelo'), 'ollama:llama3');
    await userEvent.type(screen.getByLabelText('Pregunta'), '17 x 23');
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar' }));

    expect(await screen.findByText('391')).toBeVisible();
    const request = run.mock.calls[0]?.[0];
    expect(request).toMatchObject({
      architectureId: 'alpha-v2',
      question: '17 x 23',
      fileName: '',
      settings: { pipelineVersion: '3.1', model: { provider: 'ollama', modelId: 'llama3' } },
    });
    expect(request?.taskId).toMatch(/^studio-/);
    const timeline = within(await screen.findByRole('region', { name: 'Pasos' }));
    expect(timeline.getAllByRole('button')).toHaveLength(2);

    await userEvent.click(timeline.getAllByRole('button')[1] as HTMLElement);
    const detail = within(screen.getByRole('region', { name: 'Detalle del paso' }));
    expect(detail.getByText('answer')).toBeVisible();
    expect(screen.getByText('Paso 2 de 2')).toBeVisible();
  });

  it('shows where a failed run broke', async () => {
    const failed = record({
      status: 'error',
      answer: null,
      error: 'model down',
      steps: [
        { node: 'preprocessing', durationSeconds: 0.1, error: null, updatedFields: [] },
        { node: 'reasoning', durationSeconds: 0.2, error: 'model down', updatedFields: [] },
      ],
    });
    renderRuns(
      services({
        runs: { run: () => Promise.resolve(failed), get: () => Promise.resolve(failed) },
      }),
    );
    await choose('alpha-v2');
    await userEvent.type(screen.getByLabelText('Pregunta'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar' }));
    expect(await screen.findByText('Falló en reasoning')).toBeVisible();
    expect(screen.getByText('model down', { selector: 'p' })).toBeVisible();
  });

  it('lets the user stop waiting and says the server carries on', async () => {
    const run: RunPort['run'] = (_request, signal) =>
      new Promise<RunRecord>((_resolve, reject) =>
        signal?.addEventListener('abort', () => reject(new StudioError('aborted', 'aborted'))),
      );
    renderRuns(services({ runs: { run, get: () => Promise.resolve(record()) } }));
    await choose('alpha-v2');
    await userEvent.type(screen.getByLabelText('Pregunta'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Dejar de esperar' }));
    expect(await screen.findByRole('status')).toHaveTextContent(/Dejaste de esperar/);
    expect(screen.getByRole('button', { name: 'Ejecutar' })).toBeEnabled();
  });

  it('reports a request that never produced a run', async () => {
    const run = () => Promise.reject(new StudioError('http', 'backend said no'));
    renderRuns(services({ runs: { run, get: () => Promise.resolve(record()) } }));
    await choose('alpha-v2');
    await userEvent.type(screen.getByLabelText('Pregunta'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar' }));
    expect(await screen.findByRole('alert')).toBeVisible();
  });
});

describe('GAIA questions', () => {
  it('picks a question and sends its task id and attachment', async () => {
    const run = vi.fn<RunPort['run']>(() => Promise.resolve(record()));
    renderRuns(services({ runs: { run, get: () => Promise.resolve(record()) } }));
    await choose('alpha-v2');
    await userEvent.click(screen.getByRole('button', { name: 'Elegir de GAIA' }));
    const dialog = within(await screen.findByRole('dialog', { name: 'Preguntas de GAIA' }));
    expect(await dialog.findByText('Adjunto: sheet.xlsx')).toBeVisible();
    await userEvent.click(dialog.getByRole('button', { name: /attached sheet/ }));

    expect(screen.getByText('Pregunta de GAIA')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar' }));
    await waitFor(() => expect(run).toHaveBeenCalled());
    expect(run.mock.calls[0]?.[0]).toMatchObject({ taskId: 'task-9', fileName: 'sheet.xlsx' });
  });

  it('filters the list and can be cleared', async () => {
    renderRuns(services());
    await choose('alpha-v2');
    await userEvent.click(screen.getByRole('button', { name: 'Elegir de GAIA' }));
    const dialog = within(await screen.findByRole('dialog'));
    await userEvent.type(await dialog.findByLabelText('Buscar preguntas'), 'zzz');
    expect(dialog.getByText('Ninguna pregunta coincide.')).toBeVisible();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('demo mode', () => {
  it('explains that running needs the backend and offers no GAIA questions', async () => {
    renderRuns({ ...services(), mode: 'demo' });
    expect(await screen.findByText(/modo demostración/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Elegir de GAIA' })).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Pregunta'), 'x');
    expect(screen.getByRole('button', { name: 'Ejecutar' })).toBeDisabled();
  });
});

describe('accessibility', () => {
  it('has no detectable violations with a result on screen', async () => {
    const { container } = renderRuns(services());
    await choose('alpha-v2');
    await userEvent.type(screen.getByLabelText('Pregunta'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Ejecutar' }));
    await screen.findByText('391');
    const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
