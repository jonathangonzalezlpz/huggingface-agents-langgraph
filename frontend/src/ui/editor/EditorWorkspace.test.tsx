import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import { fromDefinition } from '../../domain/editor/convert';
import { END, type EditorDocument } from '../../domain/editor/model';
import { linearDocument } from '../../domain/editor/templates';
import { StudioError } from '../../domain/errors';
import type { ValidationReport } from '../../domain/types';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { StudioServices } from '../../ports';
import { stubMatchMedia } from '../../test/setup';
import { installReactFlowMocks } from '../../test/reactFlow';
import { computeLayout } from './autoLayout';
import { EditorWorkspace, type WorkspaceProps } from './EditorWorkspace';

const base = createMemoryServices();
const catalog = await base.catalog.getCatalog();
const [summary] = await base.architectures.list();
const builtin = await base.architectures.get(summary?.id ?? '');
const { graph: v31 } = fromDefinition(builtin.definition, catalog);
const builtinDoc: EditorDocument = { graph: v31, layout: computeLayout(v31) };

beforeEach(() => {
  installReactFlowMocks();
  stubMatchMedia(false, true);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

function draftDoc(): EditorDocument {
  const doc = linearDocument('mi_agente', catalog);
  return { ...doc, layout: computeLayout(doc.graph) };
}

function renderEditor(overrides: Partial<WorkspaceProps> = {}, services: StudioServices = base) {
  const props: WorkspaceProps = {
    initialDocument: draftDoc(),
    catalog,
    readOnly: false,
    draftId: 'draft-1',
    onDuplicate: () => undefined,
    ...overrides,
  };
  return render(
    <StudioProviders services={services}>
      <MemoryRouter>
        <div style={{ width: 1200, height: 800 }}>
          <EditorWorkspace {...props} />
        </div>
      </MemoryRouter>
    </StudioProviders>,
  );
}

const canvas = () => within(document.querySelector('.react-flow') as HTMLElement);
const flowNode = (id: string) => document.querySelector(`.react-flow__node[data-id="${id}"]`);
const inspector = () => within(screen.getByRole('region', { name: 'Inspector' }));
const palette = () => within(screen.getByRole('region', { name: 'Componentes' }));
const diagnostics = () => within(screen.getByRole('region', { name: 'Diagnósticos' }));
const announced = () =>
  screen
    .getAllByRole('status')
    .map((n) => n.textContent ?? '')
    .join(' ');

async function select(id: string) {
  // A plain click: d3-drag, used by React Flow, cannot handle jsdom's synthetic mousedown.
  fireEvent.click(flowNode(id) as HTMLElement);
  await inspector().findByLabelText('Identificador');
}

describe('rendering', () => {
  it('draws the draft as nodes with their start and end markers', async () => {
    renderEditor();
    for (const id of ['preprocessing', 'reasoning', 'answer_production']) {
      await waitFor(() => expect(flowNode(id)).toBeInTheDocument());
    }
    expect(canvas().getByText('Inicio')).toBeInTheDocument();
    expect(canvas().getByText('Final')).toBeInTheDocument();
  });

  it('shows the built-in pipeline read-only, with its stored validation', () => {
    renderEditor({
      initialDocument: builtinDoc,
      readOnly: true,
      draftId: undefined as never,
      layoutKey: builtin.id,
      initialValidation: builtin.validation,
    });
    expect(flowNode('web_research')).toBeInTheDocument();
    expect(screen.getByText('Solo lectura')).toBeVisible();
    expect(diagnostics().getByText(/0 errores · 4 avisos · 1 nota/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Duplicar para editar' })).toBeEnabled();
  });
});

describe('adding components', () => {
  it('adds from the palette, selects the new node and is undoable', async () => {
    renderEditor();
    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    expect(flowNode('web_research')).toBeInTheDocument();
    expect(announced()).toContain('Componente web_research añadido');
    expect(await inspector().findByLabelText('Identificador')).toHaveValue('web_research');

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    expect(flowNode('web_research')).not.toBeInTheDocument();
    expect(announced()).toContain('Deshecho');
    await userEvent.click(screen.getByRole('button', { name: 'Rehacer' }));
    expect(flowNode('web_research')).toBeInTheDocument();
  });

  it('gives repeated components distinct ids', async () => {
    renderEditor();
    await userEvent.click(palette().getByRole('button', { name: /^reasoning/ }));
    expect(flowNode('reasoning_2')).toBeInTheDocument();
  });

  it('finds components with Ctrl+K and adds the first match with Enter', async () => {
    renderEditor();
    await userEvent.keyboard('{Control>}k{/Control}');
    const dialog = await screen.findByRole('dialog', { name: 'Añadir componente' });
    await userEvent.type(within(dialog).getByRole('combobox'), 'enciclopedia');
    expect(within(dialog).getAllByRole('option')).toHaveLength(1);
    await userEvent.keyboard('{Enter}');
    expect(flowNode('web_research')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('filters the palette and explains an empty search', async () => {
    renderEditor();
    await userEvent.type(palette().getByRole('searchbox'), 'zzz');
    expect(palette().getByText('Ningún componente coincide.')).toBeVisible();
  });

  it('offers no way to add to a read-only version', async () => {
    renderEditor({ initialDocument: builtinDoc, readOnly: true, draftId: undefined as never });
    expect(screen.queryByRole('region', { name: 'Componentes' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Añadir componente' })).toBeDisabled();
    await userEvent.keyboard('{Control>}k{/Control}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('editing a node', () => {
  it('renames a node and keeps it selected', async () => {
    renderEditor();
    await select('reasoning');
    const field = inspector().getByLabelText('Identificador');
    await userEvent.clear(field);
    await userEvent.type(field, 'pensar{Enter}');
    expect(flowNode('pensar')).toBeInTheDocument();
    expect(flowNode('reasoning')).not.toBeInTheDocument();
    expect(announced()).toContain('reasoning renombrado a pensar');
    expect(await inspector().findByLabelText('Identificador')).toHaveValue('pensar');
  });

  it('explains why a name is refused and changes nothing', async () => {
    renderEditor();
    await select('reasoning');
    const field = inspector().getByLabelText('Identificador');
    await userEvent.clear(field);
    await userEvent.type(field, 'preprocessing{Enter}');
    expect(inspector().getByText('Ya existe un nodo con ese identificador.')).toBeVisible();
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(flowNode('reasoning')).toBeInTheDocument();
  });

  it('changes the entry and deletes a node', async () => {
    renderEditor();
    await select('reasoning');
    await userEvent.click(inspector().getByRole('button', { name: 'Usar como entrada' }));
    expect(announced()).toContain('reasoning es ahora la entrada');
    expect(inspector().getByText('Es la entrada del grafo')).toBeVisible();

    await userEvent.click(inspector().getByRole('button', { name: 'Eliminar nodo' }));
    expect(flowNode('reasoning')).not.toBeInTheDocument();
    expect(inspector().getByText(/Selecciona un nodo/)).toBeVisible();
  });

  it('shows the contract of the selected component', async () => {
    renderEditor();
    await select('reasoning');
    expect(inspector().getByText('Necesita')).toBeVisible();
    expect(inspector().getByText('draft_answer')).toBeVisible();
  });
});

describe('connecting without dragging', () => {
  it('connects a direct output through the dialog', async () => {
    renderEditor();
    await select('preprocessing');
    await userEvent.click(inspector().getByRole('button', { name: 'Conectar con…' }));
    const dialog = await screen.findByRole('dialog', { name: 'Conectar preprocessing' });
    await userEvent.selectOptions(within(dialog).getByLabelText('Destino'), 'answer_production');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar' }));
    expect(announced()).toContain('preprocessing conectado con answer_production');
    expect(inspector().getByText('answer_production')).toBeVisible();
  });

  it('connects to the end and removes a connection', async () => {
    renderEditor();
    await select('answer_production');
    expect(inspector().getByText('Final')).toBeVisible();
    await userEvent.click(inspector().getByRole('button', { name: 'Quitar conexión' }));
    expect(inspector().getByText('Sin salida')).toBeVisible();
    await userEvent.click(inspector().getByRole('button', { name: 'Conectar con…' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.selectOptions(within(dialog).getByLabelText('Destino'), END);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar' }));
    expect(inspector().getByText('Final')).toBeVisible();
  });

  it('adds a decision and connects its branches one by one', async () => {
    renderEditor();
    await select('preprocessing');
    await userEvent.selectOptions(
      inspector().getByLabelText('Decisión tras este nodo'),
      'route_after_review',
    );
    expect(inspector().getAllByText('Rama sin conectar')).toHaveLength(2);

    const rows = inspector().getAllByRole('listitem');
    await userEvent.click(
      within(rows[1] as HTMLElement).getByRole('button', { name: 'Conectar con…' }),
    );
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('Rama')).toHaveValue('solve');
    await userEvent.selectOptions(within(dialog).getByLabelText('Destino'), 'reasoning');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Conectar' }));
    expect(inspector().getAllByText('Rama sin conectar')).toHaveLength(1);

    await userEvent.selectOptions(inspector().getByLabelText('Decisión tras este nodo'), '');
    expect(inspector().queryByText('Rama sin conectar')).not.toBeInTheDocument();
  });

  it('refuses to edit connections of a read-only version', async () => {
    renderEditor({ initialDocument: builtinDoc, readOnly: true, draftId: undefined as never });
    await select('router');
    expect(inspector().getByLabelText('Decisión tras este nodo')).toBeDisabled();
    for (const button of inspector().getAllByRole('button', { name: 'Conectar con…' })) {
      expect(button).toBeDisabled();
    }
    expect(inspector().getByRole('button', { name: 'Eliminar nodo' })).toBeDisabled();
  });
});

describe('keyboard shortcuts', () => {
  it('undoes with Ctrl+Z, redoes with Ctrl+Shift+Z and lays out with L', async () => {
    renderEditor();
    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    await userEvent.keyboard('{Control>}z{/Control}');
    expect(flowNode('web_research')).not.toBeInTheDocument();
    await userEvent.keyboard('{Control>}{Shift>}z{/Shift}{/Control}');
    expect(flowNode('web_research')).toBeInTheDocument();
    await userEvent.keyboard('l');
    expect(announced()).toContain('Disposición automática aplicada');
  });

  it('does not steal keys while typing in a field', async () => {
    renderEditor();
    await userEvent.type(palette().getByRole('searchbox'), 'l');
    expect(announced()).not.toContain('Disposición automática aplicada');
  });
});

describe('validation', () => {
  it('says validation is unavailable for an edited graph in demo mode', async () => {
    renderEditor();
    await userEvent.click(screen.getByRole('button', { name: 'Validar' }));
    expect(await diagnostics().findByText(/necesita el backend/)).toBeVisible();
  });

  it('lists diagnostics in plain language and jumps to the node', async () => {
    const report: ValidationReport = {
      isValid: false,
      counts: { error: 1, warning: 0, info: 0 },
      diagnostics: [
        {
          code: 'NO_PATH_TO_END',
          severity: 'error',
          message: "Node 'reasoning' has no path to END.",
          nodeId: 'reasoning',
        },
      ],
    };
    const services: StudioServices = {
      ...base,
      mode: 'live',
      validation: { validate: () => Promise.resolve(report) },
    };
    renderEditor({}, services);
    await userEvent.click(screen.getByRole('button', { name: 'Validar' }));
    expect(
      await diagnostics().findByText('Desde este nodo no se puede llegar al final.'),
    ).toBeVisible();
    expect(diagnostics().getByText(/1 error/)).toBeVisible();

    await userEvent.click(diagnostics().getByRole('button', { name: 'Ir al nodo reasoning' }));
    expect(await inspector().findByLabelText('Identificador')).toHaveValue('reasoning');
  });

  it('marks a result stale once the graph changes', async () => {
    const services: StudioServices = {
      ...base,
      validation: {
        validate: () =>
          Promise.resolve({
            isValid: true,
            counts: { error: 0, warning: 0, info: 0 },
            diagnostics: [],
          }),
      },
    };
    renderEditor({}, services);
    await userEvent.click(screen.getByRole('button', { name: 'Validar' }));
    expect(
      await diagnostics().findByText('El validador no encontró nada que señalar.'),
    ).toBeVisible();
    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    expect(diagnostics().getByText(/ha cambiado desde esta validación/)).toBeVisible();
  });

  it('reports other failures without crashing', async () => {
    const services: StudioServices = {
      ...base,
      validation: { validate: () => Promise.reject(new StudioError('network', 'down')) },
    };
    renderEditor({}, services);
    await userEvent.click(screen.getByRole('button', { name: 'Validar' }));
    expect(await diagnostics().findByText('No se pudo validar.')).toBeVisible();
  });
});

describe('persistence', () => {
  it('keeps a draft after edits, once typing settles', async () => {
    const save = vi.fn();
    const services: StudioServices = { ...base, drafts: { ...base.drafts, save } };
    renderEditor({}, services);
    expect(save).not.toHaveBeenCalled();
    await userEvent.click(palette().getByRole('button', { name: /web_research/ }));
    await waitFor(() => expect(save).toHaveBeenCalled(), { timeout: 2000 });
    const [id, saved] = save.mock.calls.at(-1) as [string, EditorDocument];
    expect(id).toBe('draft-1');
    expect(saved.graph.nodes.map((n) => n.id)).toContain('web_research');
  });

  it('stores only the layout of a read-only version after the nodes are rearranged', async () => {
    const saveLayout = vi.fn(() => Promise.resolve());
    const services: StudioServices = {
      ...base,
      layouts: { get: base.layouts.get, save: saveLayout },
    };
    const moved: EditorDocument = { ...builtinDoc, layout: {} };
    renderEditor(
      {
        initialDocument: moved,
        readOnly: true,
        draftId: undefined as never,
        layoutKey: builtin.id,
      },
      services,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Autodisposición' }));
    await waitFor(() => expect(saveLayout).toHaveBeenCalled(), { timeout: 2000 });
    const [key, layout] = saveLayout.mock.calls.at(-1) as unknown as [
      string,
      Record<string, unknown>,
    ];
    expect(key).toBe(builtin.id);
    expect(Object.keys(layout)).toHaveLength(12);
  });

  it('offers to duplicate a read-only version into an editable draft', async () => {
    const duplicate = vi.fn();
    renderEditor({
      initialDocument: builtinDoc,
      readOnly: true,
      draftId: undefined as never,
      onDuplicate: duplicate,
    });
    await userEvent.click(screen.getByRole('button', { name: 'Duplicar para editar' }));
    expect(duplicate).toHaveBeenCalledOnce();
    expect(duplicate.mock.calls[0]?.[0].graph.nodes).toHaveLength(12);
  });
});

describe('accessibility (axe) of the editor chrome', () => {
  it.each([
    ['draft', {}],
    ['read-only', { initialDocument: builtinDoc, readOnly: true, draftId: undefined as never }],
  ])('has no violations in the %s editor', async (_name, overrides) => {
    const { container } = renderEditor(overrides as Partial<WorkspaceProps>);
    await screen.findByRole('region', { name: 'Inspector' });
    // The graph canvas is the third-party library's own markup; our panels are checked.
    const results = await axe.run(
      { include: [container], exclude: [['.react-flow']] },
      { rules: { 'color-contrast': { enabled: false } } },
    );
    expect(
      results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`),
    ).toEqual([]);
  });
});
