import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { stubMatchMedia } from '../test/setup';
import { resolveTheme, THEME_STORAGE_KEY, ThemeProvider, useTheme } from './ThemeProvider';

function Probe() {
  const { preference, resolved, setPreference } = useTheme();
  return (
    <div>
      <output data-testid="state">{`${preference}:${resolved}`}</output>
      <button onClick={() => setPreference('dark')}>dark</button>
      <button onClick={() => setPreference('light')}>light</button>
      <button onClick={() => setPreference('system')}>system</button>
    </div>
  );
}

const renderProbe = () =>
  render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
const state = () => screen.getByTestId('state').textContent;

describe('resolveTheme', () => {
  it('follows the system only when the preference is system', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
  });
});

describe('ThemeProvider', () => {
  it('defaults to the system theme and applies it to the document', () => {
    stubMatchMedia(true);
    renderProbe();
    expect(state()).toBe('system:dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('reacts live to operating-system changes while following the system', () => {
    const media = stubMatchMedia(false);
    renderProbe();
    expect(document.documentElement.dataset.theme).toBe('light');
    act(() => media.setDark(true));
    expect(state()).toBe('system:dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('keeps a manual choice regardless of the system and remembers it', async () => {
    const media = stubMatchMedia(false);
    renderProbe();
    await userEvent.click(screen.getByText('dark'));
    expect(state()).toBe('dark:dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    act(() => media.setDark(false));
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('restores a stored choice on startup', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    stubMatchMedia(true);
    renderProbe();
    expect(state()).toBe('light:light');
  });

  it('returns to following the system and forgets the stored choice', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    stubMatchMedia(true);
    renderProbe();
    await userEvent.click(screen.getByText('system'));
    expect(state()).toBe('system:dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });

  it('ignores a corrupt stored value', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'neon');
    renderProbe();
    expect(state()).toBe('system:light');
  });
});
