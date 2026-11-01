import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const css = readFileSync(join(import.meta.dirname, 'tokens.css'), 'utf8');

function themeTokens(selectorPattern: RegExp): Record<string, string> {
  const block = css.match(selectorPattern)?.[1] ?? '';
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6});/g)].map((m) => [m[1], m[2]]),
  ) as Record<string, string>;
}

const themes = {
  light: themeTokens(/:root,\s*\[data-theme='light'\]\s*\{([^}]*)\}/),
  dark: themeTokens(/\[data-theme='dark'\]\s*\{([^}]*)\}/),
};

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

function contrast(foreground: string, background: string): number {
  const [a, b] = [luminance(foreground), luminance(background)].sort((x, y) => y - x);
  return ((a ?? 0) + 0.05) / ((b ?? 0) + 0.05);
}

const TEXT_PAIRS: [string, string][] = [
  ['text', 'bg'],
  ['text', 'surface'],
  ['text', 'surface-muted'],
  ['text-muted', 'bg'],
  ['text-muted', 'surface'],
  ['text-muted', 'surface-muted'],
  ['accent-text', 'surface'],
  ['accent-text', 'bg'],
  ['accent-text', 'accent-soft'],
  ['accent-contrast', 'accent'],
  ['success', 'success-soft'],
  ['warning', 'warning-soft'],
  ['error', 'error-soft'],
  ['info', 'info-soft'],
  ['success', 'surface'],
  ['warning', 'surface'],
  ['error', 'surface'],
  ['info', 'surface'],
];

const COMPONENT_PAIRS: [string, string][] = [
  ['border-strong', 'surface'],
  ['border-strong', 'bg'],
  ['accent', 'surface'],
  ['focus', 'bg'],
  ['focus', 'surface'],
  ['cat-input', 'surface'],
  ['cat-acquisition', 'surface'],
  ['cat-research', 'surface'],
  ['cat-planning', 'surface'],
  ['cat-verification', 'surface'],
  ['cat-reasoning', 'surface'],
  ['cat-output', 'surface'],
  ['cat-other', 'surface'],
];

describe.each(Object.entries(themes))('%s theme tokens', (_name, tokens) => {
  it('defines every token as a six-digit hex colour', () => {
    expect(Object.keys(tokens).length).toBeGreaterThan(25);
  });

  it.each(TEXT_PAIRS)('text token %s on %s meets 4.5:1 (WCAG 1.4.3)', (fg, bg) => {
    expect(contrast(tokens[fg] ?? '', tokens[bg] ?? '')).toBeGreaterThanOrEqual(4.5);
  });

  it.each(COMPONENT_PAIRS)('component token %s on %s meets 3:1 (WCAG 1.4.11)', (fg, bg) => {
    expect(contrast(tokens[fg] ?? '', tokens[bg] ?? '')).toBeGreaterThanOrEqual(3);
  });
});

it('defines the same token names in both themes', () => {
  expect(Object.keys(themes.dark).sort()).toEqual(Object.keys(themes.light).sort());
});

it('computes known contrast ratios correctly', () => {
  expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 1);
  expect(contrast('#777777', '#ffffff')).toBeCloseTo(4.48, 1);
});
