import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

/** jsdom has no matchMedia; tests that care about it install their own stub. */
export function stubMatchMedia(prefersDark = false) {
  const listeners = new Set<(event: { matches: boolean }) => void>();
  const state = { matches: prefersDark };
  const mediaQuery = {
    get matches() {
      return state.matches;
    },
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_type: string, listener: (event: { matches: boolean }) => void) =>
      listeners.add(listener),
    removeEventListener: (_type: string, listener: (event: { matches: boolean }) => void) =>
      listeners.delete(listener),
  };
  vi.stubGlobal('matchMedia', () => mediaQuery);
  return {
    setDark(next: boolean) {
      state.matches = next;
      listeners.forEach((listener) => listener({ matches: next }));
    },
  };
}

beforeEach(() => {
  // axe probes canvas support, which jsdom does not implement.
  HTMLCanvasElement.prototype.getContext = () => null;
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  stubMatchMedia(false);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
