import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { I18nProvider } from '../../i18n/I18nProvider';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { EditorDocument } from '../../domain/editor/model';
import type { Catalog, ParamSpec } from '../../domain/types';
import { Inspector, type InspectorActions } from './Inspector';

const spec = (over: Partial<ParamSpec> & Pick<ParamSpec, 'name' | 'kind'>): ParamSpec => ({
  default: null,
  required: false,
  minimum: null,
  maximum: null,
  maxLength: null,
  choices: [],
  ...over,
});

const contract = {
  requiredInputs: ['question'],
  optionalInputs: [],
  guaranteedOutputs: ['draft_answer'],
  optionalOutputs: [],
};

const catalog: Catalog = {
  categories: ['other'],
  components: [
    {
      implementationId: 'tunable',
      description: 'A configurable node.',
      category: 'other',
      recoverErrors: false,
      contract,
      params: [
        spec({ name: 'n', kind: 'integer', default: 2, minimum: 1, maximum: 9 }),
        spec({ name: 'mode', kind: 'enum', default: 'fast', choices: ['fast', 'slow'] }),
        spec({ name: 'flag', kind: 'boolean', default: false }),
        spec({ name: 'prompt', kind: 'text', default: 'hi', maxLength: 50 }),
        spec({ name: 'label', kind: 'string', default: null, required: true, maxLength: 8 }),
      ],
    },
    {
      implementationId: 'plain',
      description: 'Nothing to configure.',
      category: 'other',
      recoverErrors: false,
      contract,
      params: [],
    },
  ],
  routingStrategies: [],
  state: { types: ['AgentState'], fields: ['question'], initialFields: ['question'] },
};

function document(params?: Record<string, string | number | boolean>): EditorDocument {
  return {
    graph: {
      architectureId: 'a',
      schemaVersion: '4.0',
      stateType: 'AgentState',
      initialNode: 't',
      nodes: [
        {
          id: 't',
          implementationId: 'tunable',
          description: '',
          ...(params ? { params } : {}),
          outgoing: { kind: 'none' },
        },
        { id: 'p', implementationId: 'plain', description: '', outgoing: { kind: 'none' } },
      ],
    },
    layout: { t: { x: 0, y: 0 }, p: { x: 0, y: 0 } },
  };
}

function actions(): InspectorActions {
  return {
    rename: vi.fn(),
    setEntry: vi.fn(),
    remove: vi.fn(),
    openConnect: vi.fn(),
    disconnect: vi.fn(),
    setDecision: vi.fn(),
    setDescription: vi.fn(),
    setParam: vi.fn(),
    renameArchitecture: vi.fn(),
  };
}

function renderInspector(
  current: EditorDocument,
  selectedId: string,
  handlers: InspectorActions,
  readOnly = false,
) {
  return render(
    <I18nProvider>
      <Inspector
        doc={current}
        catalog={catalog}
        selectedId={selectedId}
        readOnly={readOnly}
        actions={handlers}
        availability={{ status: 'pending' }}
      />
    </I18nProvider>,
  );
}

const section = () => within(screen.getByRole('region', { name: 'Parámetros' }));

beforeEach(() => {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('the parameters section', () => {
  it('has one control per declared parameter, with the default shown', () => {
    renderInspector(document(), 't', actions());
    const params = section();
    expect(params.getByLabelText('n')).toHaveValue('2');
    expect(params.getByLabelText('mode')).toHaveValue('');
    expect(params.getByLabelText('flag')).not.toBeChecked();
    expect(params.getByLabelText('prompt')).toHaveValue('hi');
    expect(params.getByText('Predeterminado: 2')).toBeVisible();
    expect(params.getByText(/obligatorio/)).toBeVisible();
  });

  it('is absent for a component that declares none', () => {
    renderInspector(document(), 'p', actions());
    expect(screen.queryByRole('region', { name: 'Parámetros' })).not.toBeInTheDocument();
  });

  it('shows the chosen value instead of the default, and offers to reset it', () => {
    renderInspector(document({ n: 6, mode: 'slow', flag: true }), 't', actions());
    const params = section();
    expect(params.getByLabelText('n')).toHaveValue('6');
    expect(params.getByLabelText('mode')).toHaveValue('slow');
    expect(params.getByLabelText('flag')).toBeChecked();
    expect(params.getAllByRole('button', { name: 'Restablecer' })).toHaveLength(3);
  });

  it('sets a number when the field is committed with Enter', async () => {
    const handlers = actions();
    renderInspector(document(), 't', handlers);
    const field = section().getByLabelText('n');
    await userEvent.clear(field);
    await userEvent.type(field, '5{Enter}');
    expect(handlers.setParam).toHaveBeenCalledWith('t', 'n', 5);
  });

  it('explains a value outside the limits and changes nothing', async () => {
    const handlers = actions();
    renderInspector(document(), 't', handlers);
    const field = section().getByLabelText('n');
    await userEvent.clear(field);
    await userEvent.type(field, '99{Enter}');
    expect(handlers.setParam).not.toHaveBeenCalled();
    expect(await screen.findByText('Ese valor no cumple los límites del parámetro.')).toBeVisible();
    expect(field).toHaveAttribute('aria-invalid', 'true');
  });

  it('refuses text that is not a number', async () => {
    const handlers = actions();
    renderInspector(document(), 't', handlers);
    const field = section().getByLabelText('n');
    await userEvent.clear(field);
    await userEvent.type(field, 'many{Enter}');
    expect(handlers.setParam).not.toHaveBeenCalled();
    expect(await screen.findByText(/no cumple los límites/)).toBeVisible();
  });

  it('sets a checkbox and an enum, and returns the enum to its default', async () => {
    const handlers = actions();
    renderInspector(document({ mode: 'slow' }), 't', handlers);
    await userEvent.click(section().getByLabelText('flag'));
    expect(handlers.setParam).toHaveBeenCalledWith('t', 'flag', true);
    await userEvent.selectOptions(section().getByLabelText('mode'), 'fast');
    expect(handlers.setParam).toHaveBeenCalledWith('t', 'mode', 'fast');
    await userEvent.selectOptions(section().getByLabelText('mode'), '');
    expect(handlers.setParam).toHaveBeenCalledWith('t', 'mode', null);
  });

  it('resets one parameter to its default', async () => {
    const handlers = actions();
    renderInspector(document({ n: 6 }), 't', handlers);
    await userEvent.click(section().getByRole('button', { name: 'Restablecer' }));
    expect(handlers.setParam).toHaveBeenCalledWith('t', 'n', null);
  });

  it('accepts a long text up to its limit', async () => {
    const handlers = actions();
    renderInspector(document(), 't', handlers);
    const field = section().getByLabelText('prompt');
    await userEvent.clear(field);
    await userEvent.type(field, 'answer briefly');
    await userEvent.tab();
    expect(handlers.setParam).toHaveBeenCalledWith('t', 'prompt', 'answer briefly');
  });

  it('cannot be edited in a read-only view', () => {
    renderInspector(document({ n: 6 }), 't', actions(), true);
    const params = section();
    expect(params.getByLabelText('n')).toBeDisabled();
    expect(params.getByLabelText('flag')).toBeDisabled();
    expect(params.getByRole('button', { name: 'Restablecer' })).toBeDisabled();
  });

  it('has no detectable accessibility violations', async () => {
    const { container } = renderInspector(document({ n: 6 }), 't', actions());
    const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
