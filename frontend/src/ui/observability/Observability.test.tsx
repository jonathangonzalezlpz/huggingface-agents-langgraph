import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { StudioProviders } from '../../app/bootstrap';
import { StudioError } from '../../domain/errors';
import type { Insights } from '../../domain/insights';
import type { Span, Trace } from '../../domain/trace';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { StudioServices, TracePort } from '../../ports';
import { stubMatchMedia } from '../../test/setup';
import { InsightsView } from './InsightsView';
import { TraceView } from './TraceView';

const base = createMemoryServices();

function span(overrides: Partial<Span> & Pick<Span, 'id' | 'kind' | 'name'>): Span {
  return {
    parentId: null,
    status: 'ok',
    startSeconds: 0,
    durationSeconds: 1,
    attributes: {},
    error: null,
    ...overrides,
  };
}

const trace: Trace = {
  id: 'run-1',
  spans: [
    span({ id: 'r', kind: 'run', name: 'run', durationSeconds: 10 }),
    span({
      id: 'n1',
      kind: 'node',
      name: 'search',
      parentId: 'r',
      durationSeconds: 4,
      status: 'error',
      error: 'boom',
    }),
    span({
      id: 'c1',
      kind: 'llm',
      name: 'llm_call',
      parentId: 'n1',
      startSeconds: 1,
      durationSeconds: 2,
      attributes: { prompt_tokens: 10, model: 'qwen', linked_to_node: true },
    }),
    span({
      id: 'n2',
      kind: 'node',
      name: 'vote',
      parentId: 'r',
      startSeconds: 4,
      durationSeconds: 6,
    }),
  ],
  summary: {
    status: 'completed',
    durationSeconds: 10,
    nodeCount: 2,
    llmCalls: 1,
    promptTokens: 10,
    completionTokens: 3,
    errorCount: 1,
    unsupportedFigures: [],
    slowestNode: { name: 'vote', durationSeconds: 6 },
  },
};

function renderWith(ui: React.ReactElement, traces: Partial<TracePort>) {
  const services: StudioServices = {
    ...base,
    mode: 'live',
    traces: {
      getTrace: () => Promise.resolve(trace),
      getSpanPayload: () => Promise.resolve({}),
      getInsights: () => Promise.reject(new StudioError('http', 'x', 500)),
      ...traces,
    },
  };
  return render(
    <StudioProviders services={services}>
      <MemoryRouter>{ui}</MemoryRouter>
    </StudioProviders>,
  );
}

beforeEach(() => {
  stubMatchMedia(false, true);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('trace view', () => {
  it('shows the summary, one row per span and the export links by format', async () => {
    renderWith(<TraceView runId="run-1" />, {});

    expect(await screen.findByRole('button', { name: 'Ver contenido de search' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Ver contenido de vote' })).toBeVisible();
    expect(screen.getAllByText('10 s').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'JSONL' })).toHaveAttribute(
      'href',
      '/api/runs/run-1/trace.jsonl',
    );
    expect(screen.getByRole('link', { name: 'OTLP' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Markdown' })).toBeVisible();
    expect(screen.queryByText(/para analizar/i)).not.toBeInTheDocument();
  });

  it('filters to errors only', async () => {
    renderWith(<TraceView runId="run-1" />, {});
    await screen.findByRole('button', { name: 'Ver contenido de vote' });

    await userEvent.click(screen.getByRole('checkbox', { name: 'Solo errores' }));

    expect(screen.queryByRole('button', { name: 'Ver contenido de vote' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ver contenido de search' })).toBeVisible();
  });

  it('loads the content of a span only when it is opened', async () => {
    const getSpanPayload = vi.fn(() => Promise.resolve({ update: { draft_answer: 'Paris' } }));
    renderWith(<TraceView runId="run-1" />, { getSpanPayload });
    await screen.findByRole('button', { name: 'Ver contenido de vote' });
    expect(getSpanPayload).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Ver contenido de vote' }));

    await waitFor(() => expect(getSpanPayload).toHaveBeenCalledWith('run-1', 'n2'));
    expect(await screen.findByText(/Paris/)).toBeVisible();
  });

  it('shows the error of a failed span and the attributes of a model call', async () => {
    renderWith(<TraceView runId="run-1" />, {});
    await userEvent.click(await screen.findByRole('button', { name: 'Ver contenido de search' }));
    expect(await screen.findByText('Error: boom')).toBeVisible();

    await userEvent.click(screen.getByRole('button', { name: 'Ver contenido de llm_call' }));
    expect(await screen.findByText('qwen')).toBeVisible();
  });

  it('warns when a run predates per-node tracing', async () => {
    const legacy: Trace = {
      ...trace,
      spans: trace.spans.map((item) =>
        item.kind === 'llm' ? { ...item, attributes: { linked_to_node: false } } : item,
      ),
    };
    renderWith(<TraceView runId="run-1" />, { getTrace: () => Promise.resolve(legacy) });

    expect(await screen.findByText(/anterior al seguimiento por nodo/)).toBeVisible();
  });

  it('reports a failure to load the trace', async () => {
    renderWith(<TraceView runId="run-1" />, {
      getTrace: () => Promise.reject(new StudioError('http', 'x', 500)),
    });

    expect(await screen.findByRole('alert')).toBeVisible();
  });
});

const insights: Insights = {
  totals: {
    answered: 4,
    scored: 4,
    correct: 2,
    accuracy: 0.5,
    meanSeconds: 14,
    completionTokens: 50,
    technicalErrors: 1,
  },
  routes: [{ route: 'web', count: 3, scored: 3, correct: 1, accuracy: 1 / 3, meanSeconds: 12 }],
  stages: [
    { stage: 'review', totalSeconds: 48, meanSeconds: 12, tasks: 4, share: 0.6 },
    { stage: 'router', totalSeconds: 4, meanSeconds: 1, tasks: 4, share: 0.05 },
  ],
  failures: {
    wrongAnswers: 1,
    errors: [{ message: 'LLM output was truncated', count: 2 }],
    truncatedCalls: 2,
  },
  tasks: [],
  slowestTasks: [{ taskId: 't2', durationSeconds: 30, slowestStage: 'review' }],
};

describe('insights view', () => {
  it('shows totals, time per stage, routes, failures and the CSV link', async () => {
    renderWith(<InsightsView experimentId="e1" />, {
      getInsights: () => Promise.resolve(insights),
    });

    expect(await screen.findByText('50.0 %')).toBeVisible();
    expect(screen.getByRole('row', { name: /review.*60.0 %/ })).toBeVisible();
    expect(screen.getByRole('row', { name: /web.*33.3 %/ })).toBeVisible();
    expect(screen.getByText('LLM output was truncated (2)')).toBeVisible();
    expect(screen.getByText('Respuestas incorrectas: 1')).toBeVisible();
    expect(screen.getByText(/t2 · 30.0 s · etapa más lenta: review/)).toBeVisible();
    expect(screen.getByRole('link', { name: 'CSV' })).toHaveAttribute(
      'href',
      '/api/experiments/e1/trace.csv',
    );
  });

  it('reports a failure to compute the aggregates', async () => {
    renderWith(<InsightsView experimentId="e1" />, {});

    expect(await screen.findByRole('alert')).toBeVisible();
  });
});

describe('what each step did', () => {
  const withActivity: Trace = {
    ...trace,
    spans: trace.spans.map((item) =>
      item.id === 'n1'
        ? { ...item, attributes: { activity: 'fetch https://x.org/p — need the page' } }
        : item,
    ),
  };

  it('shows the one-line activity of a node under its name', async () => {
    renderWith(<TraceView runId="run-1" />, { getTrace: () => Promise.resolve(withActivity) });

    expect(await screen.findByText('fetch https://x.org/p — need the page')).toBeVisible();
  });

  it('warns about figures that the evidence does not support', async () => {
    const flagged: Trace = {
      ...withActivity,
      summary: { ...withActivity.summary, unsupportedFigures: ['568'] },
    };
    renderWith(<TraceView runId="run-1" />, { getTrace: () => Promise.resolve(flagged) });

    expect(await screen.findByText('Cifras sin respaldo en la evidencia: 568')).toBeVisible();
  });

  it('says that links were inferred when the run predates per-node tracing', async () => {
    const inferred: Trace = {
      ...trace,
      spans: trace.spans.map((item) =>
        item.kind === 'llm'
          ? { ...item, attributes: { linked_to_node: true, inferred_link: true } }
          : item,
      ),
    };
    renderWith(<TraceView runId="run-1" />, { getTrace: () => Promise.resolve(inferred) });

    expect(await screen.findByText(/se asignaron a su nodo por duración/)).toBeVisible();
    expect(screen.queryByText(/anterior al seguimiento por nodo/)).not.toBeInTheDocument();
  });
});
