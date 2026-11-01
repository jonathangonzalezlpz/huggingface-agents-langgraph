import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createLocalStorageDrafts } from '../../adapters/drafts/localStorageDrafts';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { setDecision } from '../../domain/editor/commands';
import { toDefinition } from '../../domain/editor/convert';
import type { EditorDocument } from '../../domain/editor/model';
import { blankDocument, linearDocument } from '../../domain/editor/templates';
import { StudioError } from '../../domain/errors';
import type { Architecture, ValidationReport } from '../../domain/types';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { SaveResult, StudioServices } from '../../ports';
import { stubMatchMedia } from '../../test/setup';
import { installReactFlowMocks } from '../../test/reactFlow';
import { computeLayout } from './autoLayout';
import { EditorWorkspace, type WorkspaceProps } from './EditorWorkspace';

const base = createMemoryServices();
const catalog = await base.catalog.getCatalog();
const [summary] = await base.architectures.list();
const builtin = await base.architectures.get(summary?.id ?? '');

const emptyReport = (over: Partial<ValidationReport> = {}): ValidationReport => ({
  isValid: true,
  counts: { error: 0, warning: 0, info: 0 },
  diagnostics: [],
  availability: {},
  ...over,
});

function fakeStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, value),
  };
}

function saved(version: number, validation = emptyReport()): SaveResult {
  const architecture: Architecture = {
    ...builtin,
    id: `version-${version}`,
    architectureId: 'mi_agente',
    version,
    readOnly: false,
    validation,
  };
  return { architecture, created: true };
}

beforeEach(() => {
  installReactFlowMocks();
  stubMatchMedia(false, true);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

function draft(): EditorDocument {
  const doc = linearDocument('mi_agente', catalog);
  return { ...doc, layout: computeLayout(doc.graph) };
}

function servicesWith(overrides: Partial<StudioServices> = {}): StudioServices {
  return {
    ...base,
    mode: 'live',
    drafts: createLocalStorageDrafts(fakeStorage()),
    ...overrides,
  };
}

function renderEditor(services: StudioServices, props: Partial<WorkspaceProps> = {}) {
  const initialDocument = props.initialDocument ?? draft();
  if (props.draftId !== undefined || !('draftId' in props)) {
    services.drafts.save('draft-1', initialDocument);
  }
  return render(
    <StudioProviders services={services}>
      <MemoryRouter>
        <div style={{ width: 1200, height: 800 }}>
          <EditorWorkspace
            initialDocument={initialDocument}
            catalog={catalog}
            readOnly={false}
            draftId="draft-1"
            onEdit={() => undefined}
            {...props}
          />
        </div>
      </MemoryRouter>
    </StudioProviders>,
  );
}

const inspector = () => within(screen.getByRole('region', { name: 'Inspector' }));
const palette = () => within(screen.getByRole('region', { name: 'Componentes' }));
const diagnostics = () => within(screen.getByRole('region', { name: 'Diagnósticos' }));
const toolbar = () => within(screen.getByRole('toolbar'));
const flowNode = (id: string) => document.querySelector(`.react-flow__node[data-id="${id}"]`);

async function select(id: string) {
  fireEvent.click(flowNode(id) as HTMLElement);
  await inspector().findByLabelText('Identificador');
}

describe('saving a version', () => {
  it('saves, reports the version and shows it as saved until the draft changes', async () => {
    const save = vi.fn(() => Promise.resolve(saved(1)));
    const services = servicesWith({ architectures: { ...base.architectures, save } });
    renderEditor(services);
    expect(screen.getByText('Sin guardar')).toBeVisible();

    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText('Versión 1 guardada.')).toBeVisible();
    expect(screen.getByText('Guardado como v1')).toBeVisible();
    expect(save).toHaveBeenCalledOnce();
    const sent = (
      save.mock.calls[0] as unknown as [{ architectureId: string; nodes: unknown[] }]
    )[0];
    expect(sent.architectureId).toBe('mi_agente');
    expect(sent.nodes).toHaveLength(3);
    expect(services.drafts.savedMarker('draft-1')).toMatchObject({
      versionId: 'version-1',
      version: 1,
    });

    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    expect(screen.getByText('Sin guardar')).toBeVisible();
  });

  it('does not call the layout a change: moving nodes leaves the draft saved', async () => {
    const save = vi.fn(() => Promise.resolve(saved(1)));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    await screen.findByText('Guardado como v1');
    await userEvent.click(toolbar().getByRole('button', { name: 'Autodisposición' }));
    expect(screen.getByText('Guardado como v1')).toBeVisible();
  });

  it('says when identical content already existed', async () => {
    const save = vi.fn(() => Promise.resolve({ ...saved(2), created: false }));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText('Ya existía como versión 2: no se creó otra.')).toBeVisible();
  });

  it('warns that the saved version has validation errors', async () => {
    const withError = saved(
      1,
      emptyReport({ isValid: false, counts: { error: 2, warning: 0, info: 0 } }),
    );
    const save = vi.fn(() => Promise.resolve(withError));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText(/tiene 2 errores de validación/)).toBeVisible();
  });

  it('warns about decisions that have no connected branch and will not be stored', async () => {
    const decided = setDecision(draft(), catalog, 'preprocessing', 'route_after_review');
    if (!decided.ok) throw new Error('setup');
    const save = vi.fn(() => Promise.resolve(saved(1)));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }), {
      initialDocument: decided.doc,
    });
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText(/no se guardan: preprocessing/)).toBeVisible();
  });

  it('refuses to save an empty graph without calling the backend', async () => {
    const save = vi.fn(() => Promise.resolve(saved(1)));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }), {
      initialDocument: blankDocument('vacio'),
    });
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText('Añade al menos un componente antes de guardar.')).toBeVisible();
    expect(save).not.toHaveBeenCalled();
  });

  it('explains that saving needs the backend in demo mode', async () => {
    renderEditor({ ...servicesWith(), mode: 'demo' });
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText(/Guardar necesita el backend/)).toBeVisible();
  });

  it('reports any other failure without losing the draft', async () => {
    const services = servicesWith({
      architectures: {
        ...base.architectures,
        save: () => Promise.reject(new StudioError('network', 'down')),
      },
    });
    renderEditor(services);
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    expect(await screen.findByText('No se pudo guardar la versión.')).toBeVisible();
    expect(screen.getByText('Sin guardar')).toBeVisible();
    expect(services.drafts.load('draft-1')).not.toBeNull();
  });

  it('saves with Ctrl+S', async () => {
    const save = vi.fn(() => Promise.resolve(saved(1)));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.keyboard('{Control>}s{/Control}');
    await waitFor(() => expect(save).toHaveBeenCalledOnce());
  });

  it('offers no save button for a version that is not a draft', () => {
    renderEditor(servicesWith(), { readOnly: true, draftId: undefined as never });
    expect(screen.queryByRole('button', { name: 'Guardar versión' })).not.toBeInTheDocument();
  });
});

describe('live validation', () => {
  it('validates after edits settle and shows the result without pressing anything', async () => {
    const validate = vi.fn(() =>
      Promise.resolve(
        emptyReport({
          isValid: false,
          counts: { error: 1, warning: 0, info: 0 },
          diagnostics: [
            { code: 'NO_PATH_TO_END', severity: 'error', message: 'x', nodeId: 'reasoning' },
          ],
        }),
      ),
    );
    renderEditor(servicesWith({ validation: { validate } }));
    expect(
      await diagnostics().findByText(
        'Desde este nodo no se puede llegar al final.',
        {},
        { timeout: 3000 },
      ),
    ).toBeVisible();
    const before = validate.mock.calls.length;

    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    await waitFor(() => expect(validate.mock.calls.length).toBeGreaterThan(before), {
      timeout: 3000,
    });
    const definition = (validate.mock.calls.at(-1) as unknown as [{ nodes: { id: string }[] }])[0];
    expect(definition.nodes.map((n) => n.id)).toContain('web_research');
  });

  it('ignores a slow response that a newer request has already replaced', async () => {
    const resolvers: ((report: ValidationReport) => void)[] = [];
    const validate = vi.fn(
      () => new Promise<ValidationReport>((resolve) => resolvers.push(resolve)),
    );
    renderEditor(servicesWith({ validation: { validate } }));
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(1), { timeout: 3000 });
    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(2), { timeout: 3000 });

    const newer = emptyReport({ counts: { error: 0, warning: 3, info: 0 } });
    const older = emptyReport({ counts: { error: 9, warning: 0, info: 0 } });
    resolvers[1]?.(newer);
    expect(await diagnostics().findByText(/3 avisos/)).toBeVisible();
    resolvers[0]?.(older);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(diagnostics().queryByText(/9 errores/)).not.toBeInTheDocument();
    expect(diagnostics().getByText(/3 avisos/)).toBeVisible();
  });

  it('stops retrying in demo mode but still lets the user ask explicitly', async () => {
    const validate = vi.fn(() => Promise.reject(new StudioError('unavailable', 'demo')));
    renderEditor({ ...servicesWith({ validation: { validate } }), mode: 'demo' });
    expect(
      await diagnostics().findByText(/necesita el backend/, {}, { timeout: 3000 }),
    ).toBeVisible();
    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(validate).toHaveBeenCalledTimes(1);
    await userEvent.click(toolbar().getByRole('button', { name: 'Validar' }));
    await waitFor(() => expect(validate).toHaveBeenCalledTimes(2));
  });

  it('does not validate a read-only version, which already has its stored report', async () => {
    const validate = vi.fn(() => Promise.resolve(emptyReport()));
    renderEditor(servicesWith({ validation: { validate } }), {
      initialDocument: { graph: draft().graph, layout: draft().layout },
      readOnly: true,
      draftId: undefined as never,
      initialValidation: emptyReport({ counts: { error: 0, warning: 4, info: 1 } }),
    });
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(validate).not.toHaveBeenCalled();
    expect(diagnostics().getByText(/4 avisos/)).toBeVisible();
  });
});

describe('data available at a node', () => {
  const report = emptyReport({
    availability: {
      preprocessing: { guaranteed: ['file_name', 'question', 'task_id'], possible: [] },
      reasoning: { guaranteed: ['question'], possible: ['file_path'] },
    },
  });

  it('lists what is guaranteed and what exists only on some paths', async () => {
    renderEditor(servicesWith({ validation: { validate: () => Promise.resolve(report) } }));
    await diagnostics().findByText(/0 errores/, {}, { timeout: 3000 });
    await select('reasoning');
    const section = within(inspector().getByRole('region', { name: 'Datos aquí' }));
    expect(section.getByText('Garantizados en todos los caminos')).toBeVisible();
    expect(section.getByText('question')).toBeVisible();
    expect(section.getByText('file_path')).toBeVisible();
    expect(section.getByText('Solo en algunos caminos')).toBeVisible();
  });

  it('says so when no path reaches the node', async () => {
    renderEditor(servicesWith({ validation: { validate: () => Promise.resolve(report) } }));
    await diagnostics().findByText(/0 errores/, {}, { timeout: 3000 });
    await select('answer_production');
    expect(inspector().getByText('Ningún camino llega a este nodo.')).toBeVisible();
  });

  it('is honest when it cannot be known', async () => {
    renderEditor({ ...servicesWith(), mode: 'demo' });
    await diagnostics().findByText(/necesita el backend/, {}, { timeout: 3000 });
    await select('reasoning');
    expect(inspector().getByText('No disponible sin el backend.')).toBeVisible();
  });
});

describe('inspector fields', () => {
  it('edits a node description and keeps it when the node is selected again', async () => {
    renderEditor(servicesWith());
    await select('reasoning');
    const field = inspector().getByLabelText('Descripción');
    await userEvent.type(field, 'Razona con calma');
    fireEvent.blur(field);
    await select('preprocessing');
    await select('reasoning');
    expect(inspector().getByLabelText('Descripción')).toHaveValue('Razona con calma');
  });

  it('refuses a description that is too long and explains why', async () => {
    renderEditor(servicesWith());
    await select('reasoning');
    const field = inspector().getByLabelText('Descripción');
    fireEvent.change(field, { target: { value: 'x'.repeat(501) } });
    fireEvent.blur(field);
    expect(await inspector().findByText('La descripción es demasiado larga.')).toBeVisible();
  });

  it('renames the architecture and refuses the reserved name', async () => {
    renderEditor(servicesWith());
    const name = inspector().getByLabelText('Nombre de la arquitectura');
    await userEvent.clear(name);
    await userEvent.type(name, 'gaia_v31{Enter}');
    expect(
      await inspector().findByText('Ese nombre está reservado para la arquitectura integrada.'),
    ).toBeVisible();
    await userEvent.clear(name);
    await userEvent.type(name, 'otro_agente{Enter}');
    expect(await screen.findByRole('heading', { level: 1, name: 'otro_agente' })).toBeVisible();
  });

  it('shows the architecture name read-only for a version that cannot change', () => {
    renderEditor(servicesWith(), { readOnly: true, draftId: undefined as never });
    expect(inspector().getByLabelText('Nombre de la arquitectura')).toBeDisabled();
  });
});

describe('editing a version', () => {
  it('names the action after what it does', () => {
    const edit = vi.fn();
    const { unmount } = renderEditor(servicesWith(), {
      readOnly: true,
      draftId: undefined as never,
      editLabel: 'editor.edit',
      onEdit: edit,
    });
    expect(screen.getByText(/Pulsa Editar para crear un borrador/)).toBeVisible();
    fireEvent.click(toolbar().getByRole('button', { name: 'Editar' }));
    expect(edit).toHaveBeenCalledOnce();
    unmount();

    renderEditor(servicesWith(), { readOnly: true, draftId: undefined as never });
    expect(toolbar().getByRole('button', { name: 'Duplicar para editar' })).toBeVisible();
    expect(toDefinition(draft().graph).nodes).toHaveLength(3);
  });
});
