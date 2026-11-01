import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { createMemoryServices } from '../adapters/memory/memoryServices';
import { StudioError } from '../domain/errors';
import { LANGUAGE_STORAGE_KEY } from '../i18n';
import type { StudioServices } from '../ports';
import { stubMatchMedia } from '../test/setup';
import { THEME_STORAGE_KEY } from '../theme/ThemeProvider';
import { AppRoutes } from './AppRoutes';
import { chooseMode, StudioProviders } from './bootstrap';

function renderApp(path = '/builder', services: StudioServices = createMemoryServices()) {
  return render(
    <StudioProviders services={services}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </StudioProviders>,
  );
}

async function accessibilityViolations(container: HTMLElement) {
  // jsdom has no layout engine, so colour contrast is verified separately against the tokens.
  const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`);
}

describe('navigation and structure', () => {
  it('redirects the root to the builder', async () => {
    renderApp('/');
    expect(
      await screen.findByRole('heading', { level: 1, name: /constructor|builder/i }),
    ).toBeVisible();
  });

  it('exposes landmarks, a skip link and the four sections', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    expect(screen.getByRole('link', { name: 'Saltar al contenido' })).toHaveAttribute(
      'href',
      '#main',
    );
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual([
      'Constructor',
      'Ejecuciones',
      'Experimentos',
      'Sistema',
    ]);
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Constructor' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('navigates between sections', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    await userEvent.click(screen.getByRole('link', { name: 'Sistema' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Sistema' })).toBeVisible();
    await userEvent.click(screen.getByRole('link', { name: 'Ejecuciones' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Ejecuciones' })).toBeVisible();
  });

  it('shows a helpful page for unknown addresses', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp('/nope');
    expect(await screen.findByRole('heading', { name: 'Página no encontrada' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Volver al Constructor' })).toHaveAttribute(
      'href',
      '/builder',
    );
  });

  it('links to the previous interface while both coexist', () => {
    renderApp();
    const legacy = screen.getAllByRole('link', { name: /interfaz anterior|previous interface/i });
    expect(legacy[0]).toHaveAttribute('href', '/');
  });
});

describe('builder page', () => {
  it('lists the built-in architecture with its validation summary', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    const library = await screen.findByRole('region', { name: 'Biblioteca de arquitecturas' });
    expect(await within(library).findByRole('heading', { name: 'gaia_v31' })).toBeVisible();
    expect(within(library).getByText('Válida')).toBeVisible();
    expect(within(library).getByText('Solo lectura')).toBeVisible();
    expect(within(library).getByText(/12 componentes/)).toBeVisible();
    expect(within(library).getByText(/0 errores · 4 avisos · 1 nota/)).toBeVisible();
  });

  it('shows the component catalog grouped by category', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    const acquisition = await screen.findByRole('region', { name: 'Adquisición' });
    expect(within(acquisition).getAllByRole('listitem')).toHaveLength(5);
    expect(within(acquisition).getAllByText('Recupera errores')).toHaveLength(5);
    expect(screen.getByRole('region', { name: 'Entrada' })).toBeVisible();
  });

  it('describes components in the selected language', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    const input = await screen.findByRole('region', { name: 'Entrada' });
    expect(within(input).getByText(/Normaliza espacios/)).toBeVisible();
    await userEvent.click(screen.getByRole('radio', { name: 'English' }));
    expect(await screen.findByText(/Normalizes whitespace/)).toBeVisible();
    expect(screen.queryByText(/Normaliza espacios/)).not.toBeInTheDocument();
  });

  it('falls back to the backend description for components without a translation', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    const base = createMemoryServices();
    const catalog = await base.catalog.getCatalog();
    renderApp('/builder', {
      ...base,
      catalog: {
        getCatalog: () =>
          Promise.resolve({
            ...catalog,
            components: [
              ...catalog.components,
              {
                implementationId: 'brand_new_component',
                description: 'Backend-provided text',
                category: 'other',
                recoverErrors: false,
                contract: {
                  requiredInputs: [],
                  optionalInputs: [],
                  guaranteedOutputs: [],
                  optionalOutputs: [],
                },
              },
            ],
          }),
      },
    });
    const other = await screen.findByRole('region', { name: 'Otros' });
    expect(within(other).getByText('brand_new_component')).toBeVisible();
    expect(within(other).getByText('Backend-provided text')).toBeVisible();
  });

  it('explains backend failures and allows retrying', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    let attempts = 0;
    const base = createMemoryServices();
    const flaky: StudioServices = {
      ...base,
      catalog: {
        getCatalog: () => {
          attempts += 1;
          return attempts === 1
            ? Promise.reject(new StudioError('network', 'down'))
            : base.catalog.getCatalog();
        },
      },
    };
    renderApp('/builder', flaky);
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('No se puede conectar con el backend.');
    await userEvent.click(within(alert).getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('region', { name: 'Adquisición' })).toBeVisible();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('reports http failures with their status', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    const base = createMemoryServices();
    renderApp('/builder', {
      ...base,
      architectures: {
        list: () => Promise.reject(new StudioError('http', 'boom', 503)),
        get: base.architectures.get,
        save: base.architectures.save,
      },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'El backend respondió con un error (503).',
    );
  });
});

describe('preferences', () => {
  it('switches language immediately and remembers it', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    expect(screen.getAllByRole('heading', { level: 1 })[0]).toHaveTextContent('Constructor');
    await userEvent.click(screen.getByRole('radio', { name: 'English' }));
    expect(screen.getAllByRole('heading', { level: 1 })[0]).toHaveTextContent('Builder');
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
  });

  it('follows the system theme and lets the user override it in one click', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    stubMatchMedia(true);
    renderApp();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('radio', { name: 'Sistema' })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: 'Claro' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });
});

describe('system status and modes', () => {
  it('shows backend and model state with text, not colour alone', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    const base = createMemoryServices();
    renderApp('/builder', {
      ...base,
      mode: 'live',
      system: {
        getStatus: () =>
          Promise.resolve({ backend: 'online', llm: { state: 'sleeping', name: 'LLM' } }),
      },
    });
    const status = screen.getByRole('region', { name: 'Estado' });
    expect(await within(status).findByText('Conectado')).toBeVisible();
    expect(within(status).getByText('En reposo')).toBeVisible();
  });

  it('flags an unreachable backend', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    const base = createMemoryServices();
    renderApp('/builder', {
      ...base,
      system: { getStatus: () => Promise.resolve({ backend: 'offline', llm: null }) },
    });
    expect(await screen.findByText('Sin conexión')).toBeVisible();
    expect(screen.getByText('Sin datos')).toBeVisible();
  });

  it('announces demo mode permanently', () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    renderApp();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Modo demostración: datos de ejemplo; las ejecuciones no son reales.',
    );
  });

  it('does not show the demo banner against the real backend', () => {
    renderApp('/builder', { ...createMemoryServices(), mode: 'live' });
    expect(screen.queryByText(/demostración|Demo mode/i)).not.toBeInTheDocument();
  });

  it('chooses the mode from the build or the address', () => {
    expect(chooseMode('', undefined)).toBe('live');
    expect(chooseMode('?demo=1', undefined)).toBe('demo');
    expect(chooseMode('?demo=0', undefined)).toBe('live');
    expect(chooseMode('', 'demo')).toBe('demo');
  });
});

describe('accessibility (axe, structure and semantics)', () => {
  it.each(['/builder', '/runs', '/experiments', '/system', '/nope'])(
    'has no violations on %s in both languages',
    async (path) => {
      for (const language of ['es', 'en']) {
        localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
        const { container, unmount } = renderApp(path);
        await waitFor(() => expect(screen.getAllByRole('heading').length).toBeGreaterThan(0));
        await screen.findAllByText(/./);
        expect(await accessibilityViolations(container)).toEqual([]);
        unmount();
      }
    },
  );

  it('has no violations once the library and catalog have loaded', async () => {
    const { container } = renderApp('/builder');
    await screen.findByRole('region', { name: /adquisición|acquisition/i });
    expect(await accessibilityViolations(container)).toEqual([]);
  });
});
