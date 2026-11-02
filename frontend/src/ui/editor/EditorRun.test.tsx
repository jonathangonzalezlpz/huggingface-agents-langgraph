import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createLocalStorageDrafts } from '../../adapters/drafts/localStorageDrafts';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import type { EditorDocument } from '../../domain/editor/model';
import { linearDocument } from '../../domain/editor/templates';
import type { Architecture, ValidationReport } from '../../domain/types';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { SaveResult, StudioServices } from '../../ports';
import { installReactFlowMocks } from '../../test/reactFlow';
import { stubMatchMedia } from '../../test/setup';
import { computeLayout } from './autoLayout';
import { EditorWorkspace, type WorkspaceProps } from './EditorWorkspace';

const base = createMemoryServices();
const catalog = await base.catalog.getCatalog();
const [summary] = await base.architectures.list();
const builtin = await base.architectures.get(summary?.id ?? '');

const report = (errors: number): ValidationReport => ({
  isValid: errors === 0,
  counts: { error: errors, warning: 0, info: 0 },
  diagnostics: [],
  availability: {},
});

function saved(errors = 0): SaveResult {
  const architecture: Architecture = {
    ...builtin,
    id: 'version-1',
    architectureId: 'mi_agente',
    version: 1,
    readOnly: false,
    validation: report(errors),
  };
  return { architecture, created: true };
}

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

function draft(): EditorDocument {
  const doc = linearDocument('mi_agente', catalog);
  return { ...doc, layout: computeLayout(doc.graph) };
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderEditor(
  services: StudioServices,
  props: Partial<WorkspaceProps> = {},
  asDraft = true,
) {
  const initialDocument = props.initialDocument ?? draft();
  if (asDraft) services.drafts.save('draft-1', initialDocument);
  return render(
    <StudioProviders services={services}>
      <MemoryRouter initialEntries={['/builder']}>
        <Where />
        <div style={{ width: 1200, height: 800 }}>
          <EditorWorkspace
            initialDocument={initialDocument}
            catalog={catalog}
            readOnly={false}
            {...(asDraft ? { draftId: 'draft-1' } : {})}
            onEdit={() => undefined}
            {...props}
          />
        </div>
      </MemoryRouter>
    </StudioProviders>,
  );
}

function servicesWith(overrides: Partial<StudioServices> = {}): StudioServices {
  return { ...base, mode: 'live', drafts: createLocalStorageDrafts(fakeStorage()), ...overrides };
}

const toolbar = () => within(screen.getByRole('toolbar'));
const where = () => screen.getByTestId('where');

beforeEach(() => {
  installReactFlowMocks();
  stubMatchMedia(false, true);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('running from a draft', () => {
  it('saves first, then opens the runs page with the new version', async () => {
    const save = vi.fn(() => Promise.resolve(saved()));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar y ejecutar' }));
    expect(save).toHaveBeenCalledOnce();
    await waitFor(() => expect(where()).toHaveTextContent('/runs?architecture=version-1'));
  });

  it('stays in the editor when the saved version has errors', async () => {
    const save = vi.fn(() => Promise.resolve(saved(2)));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar y ejecutar' }));
    expect(await screen.findByText(/2 errores de validación/)).toBeVisible();
    expect(where()).toHaveTextContent('/builder');
  });

  it('runs a saved, unchanged draft without saving again', async () => {
    const save = vi.fn(() => Promise.resolve(saved()));
    renderEditor(servicesWith({ architectures: { ...base.architectures, save } }));
    await userEvent.click(toolbar().getByRole('button', { name: 'Guardar versión' }));
    await screen.findByText('Guardado como v1');
    await userEvent.click(toolbar().getByRole('button', { name: 'Ejecutar' }));
    expect(save).toHaveBeenCalledOnce();
    expect(where()).toHaveTextContent('/runs?architecture=version-1');
  });

  it('is disabled in the demo, which has no backend', () => {
    renderEditor({ ...servicesWith(), mode: 'demo' });
    expect(toolbar().getByRole('button', { name: 'Guardar y ejecutar' })).toBeDisabled();
  });
});

describe('running a stored version', () => {
  const readOnlyProps = (validation: ValidationReport): Partial<WorkspaceProps> => ({
    readOnly: true,
    runVersionId: 'alpha-v2',
    layoutKey: 'alpha-v2',
    initialValidation: validation,
  });

  it('opens the runs page with that version selected', async () => {
    renderEditor(servicesWith(), readOnlyProps(report(0)), false);
    await userEvent.click(toolbar().getByRole('button', { name: 'Ejecutar' }));
    expect(where()).toHaveTextContent('/runs?architecture=alpha-v2');
  });

  it('cannot run a version with errors', () => {
    renderEditor(servicesWith(), readOnlyProps(report(1)), false);
    expect(toolbar().getByRole('button', { name: 'Ejecutar' })).toBeDisabled();
  });
});
