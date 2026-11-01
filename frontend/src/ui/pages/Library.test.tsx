import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { StudioProviders } from '../../app/bootstrap';
import { createLocalStorageDrafts } from '../../adapters/drafts/localStorageDrafts';
import { createMemoryServices } from '../../adapters/memory/memoryServices';
import type { AgentDefinition, Architecture, ArchitectureSummary } from '../../domain/types';
import { blankDocument } from '../../domain/editor/templates';
import { LANGUAGE_STORAGE_KEY } from '../../i18n';
import type { StudioServices } from '../../ports';
import { BuilderPage } from './BuilderPage';

const base = createMemoryServices();
const [builtinSummary] = await base.architectures.list();
const builtin = await base.architectures.get(builtinSummary?.id ?? '');

function definition(chain: string[]): AgentDefinition {
  return {
    schemaVersion: '4.0',
    architectureId: 'alpha',
    stateType: 'AgentState',
    initialNode: chain[0] ?? '',
    nodes: chain.map((id) => ({ id, implementationId: id, description: '' })),
    edges: chain.map((id, index) => ({
      type: 'direct' as const,
      source: id,
      target: chain[index + 1] ?? '__end__',
    })),
  };
}

function version(number: number, chain: string[]): Architecture {
  return {
    id: `alpha-v${number}`,
    architectureId: 'alpha',
    version: number,
    parentId: number > 1 ? `alpha-v${number - 1}` : null,
    contentSha256: `${number}`.repeat(64),
    createdAt: `2026-11-0${number}T10:00:00Z`,
    readOnly: false,
    definition: definition(chain),
    validation: {
      isValid: number === 2,
      counts: { error: number === 2 ? 0 : 1, warning: 0, info: 0 },
      diagnostics: [],
      availability: {},
    },
  };
}

const v1 = version(1, ['preprocessing', 'reasoning']);
const v2 = version(2, ['preprocessing', 'reasoning', 'answer_production']);

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

function services(): StudioServices {
  const all = [builtin, v1, v2];
  return {
    ...base,
    mode: 'live',
    drafts: createLocalStorageDrafts(fakeStorage()),
    architectures: {
      list: () =>
        Promise.resolve(
          all.map(
            (item) =>
              Object.fromEntries(
                Object.entries(item).filter(
                  ([key]) => key !== 'definition' && key !== 'validation',
                ),
              ) as unknown as ArchitectureSummary,
          ),
        ),
      get: (id) => {
        const found = all.find((item) => item.id === id);
        return found ? Promise.resolve(found) : Promise.reject(new Error('missing'));
      },
      save: base.architectures.save,
    },
  };
}

function DraftProbe() {
  const { id } = useParams();
  return <p>opened draft {id}</p>;
}

function renderLibrary(current: StudioServices) {
  return render(
    <StudioProviders services={current}>
      <MemoryRouter initialEntries={['/builder']}>
        <Routes>
          <Route path="/builder" element={<BuilderPage />} />
          <Route path="/builder/draft/:id" element={<DraftProbe />} />
        </Routes>
      </MemoryRouter>
    </StudioProviders>,
  );
}

const library = async () =>
  within(await screen.findByRole('region', { name: 'Biblioteca de arquitecturas' }));

beforeEach(() => {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
});

describe('library grouped by architecture', () => {
  it('shows one card per architecture with its latest version', async () => {
    renderLibrary(services());
    const lib = await library();
    expect(await lib.findByRole('heading', { name: 'alpha' })).toBeVisible();
    expect(lib.getAllByRole('heading', { level: 3 })).toHaveLength(2);
    expect(lib.getByText(/Última: v2/)).toBeVisible();
    expect(lib.getByText(/Integrada/)).toBeVisible();
  });

  it('lists the built-in pipeline first and gives it no history', async () => {
    renderLibrary(services());
    const lib = await library();
    await lib.findByRole('heading', { name: 'alpha' });
    const headings = lib.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual(['gaia_v31', 'alpha']);
    expect(lib.getAllByText(/Historial/)).toHaveLength(1);
  });

  it('summarizes what each version changed', async () => {
    renderLibrary(services());
    const lib = await library();
    await lib.findByRole('heading', { name: 'alpha' });
    expect(lib.getByText('Historial · 2 versiones')).toBeVisible();
    expect(lib.getByText('Versión inicial')).toBeInTheDocument();
    expect(
      lib.getByText('1 nodo añadido, 2 conexiones añadidas, 1 conexión eliminada'),
    ).toBeInTheDocument();
    const [first] = lib.getAllByRole('link', { name: 'Abrir alpha v2' });
    expect(first).toHaveAttribute('href', '/builder/architecture/alpha-v2');
    expect(lib.getByRole('link', { name: 'Abrir alpha v1' })).toHaveAttribute(
      'href',
      '/builder/architecture/alpha-v1',
    );
  });

  it('opens the latest version from the card', async () => {
    renderLibrary(services());
    const lib = await library();
    expect(await lib.findByRole('link', { name: 'Abrir alpha' })).toHaveAttribute(
      'href',
      '/builder/architecture/alpha-v2',
    );
  });
});

describe('editing from the library', () => {
  it('creates a draft with the same name, linked to the version it came from', async () => {
    const current = services();
    renderLibrary(current);
    const lib = await library();
    await userEvent.click(await lib.findByRole('button', { name: 'Editar alpha' }));

    const opened = await screen.findByText(/opened draft/);
    const id = opened.textContent?.replace('opened draft ', '') ?? '';
    expect(current.drafts.load(id)?.graph.architectureId).toBe('alpha');
    expect(current.drafts.load(id)?.graph.nodes.map((n) => n.id)).toEqual([
      'preprocessing',
      'reasoning',
      'answer_production',
    ]);
    expect(current.drafts.savedMarker(id)).toMatchObject({ versionId: 'alpha-v2', version: 2 });
  });

  it('copies the built-in pipeline under a new name, with no saved marker', async () => {
    const current = services();
    renderLibrary(current);
    const lib = await library();
    await userEvent.click(
      await lib.findByRole('button', { name: 'Duplicar para editar gaia_v31' }),
    );

    const opened = await screen.findByText(/opened draft/);
    const id = opened.textContent?.replace('opened draft ', '') ?? '';
    expect(current.drafts.load(id)?.graph.architectureId).toBe('gaia_v31_copy');
    expect(current.drafts.savedMarker(id)).toBeNull();
  });

  it('numbers a copy when a draft with that name already exists', async () => {
    const current = services();
    current.drafts.save('earlier', blankDocument('gaia_v31_copy'));
    renderLibrary(current);
    const lib = await library();
    await userEvent.click(
      await lib.findByRole('button', { name: 'Duplicar para editar gaia_v31' }),
    );
    await screen.findByText(/opened draft/);
    expect(
      current.drafts
        .list()
        .map((d) => d.architectureId)
        .sort(),
    ).toEqual(['gaia_v31_copy', 'gaia_v31_copy_2']);
  });
});
