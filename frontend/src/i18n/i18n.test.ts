import { describe, expect, it } from 'vitest';

import { detectLanguage, messageKeys, translate, translatePlural } from './index';

describe('catalogs', () => {
  it('provide exactly the same keys in both languages', () => {
    expect(messageKeys('en').sort()).toEqual(messageKeys('es').sort());
  });

  it('never leave a message empty', () => {
    for (const language of ['es', 'en'] as const) {
      for (const key of messageKeys(language)) {
        expect(translate(language, key as never).trim(), `${language}:${key}`).not.toBe('');
      }
    }
  });

  it('keep the same placeholders in every language', () => {
    const placeholders = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort();
    for (const key of messageKeys('es')) {
      expect(placeholders(translate('en', key as never)), key).toEqual(
        placeholders(translate('es', key as never)),
      );
    }
  });

  it('give every plural family both variants', () => {
    const keys = messageKeys('es');
    for (const key of keys.filter((k) => k.endsWith('.one'))) {
      expect(keys).toContain(key.replace(/\.one$/, '.other'));
    }
  });
});

describe('translate', () => {
  it('interpolates parameters and leaves unknown placeholders visible', () => {
    expect(translate('en', 'error.http', { status: 503 })).toBe(
      'The backend responded with an error (503).',
    );
    expect(translate('en', 'error.http')).toContain('{status}');
  });

  it('chooses singular and plural forms per language', () => {
    expect(translatePlural('es', 'diagnostics.errors', 1)).toBe('1 error');
    expect(translatePlural('es', 'diagnostics.errors', 3)).toBe('3 errores');
    expect(translatePlural('en', 'diagnostics.warnings', 1)).toBe('1 warning');
    expect(translatePlural('en', 'diagnostics.warnings', 0)).toBe('0 warnings');
  });
});

describe('detectLanguage', () => {
  it('prefers an explicit stored choice', () => {
    expect(detectLanguage('en', ['es-ES'])).toBe('en');
  });

  it('uses the first supported browser language, ignoring regions and case', () => {
    expect(detectLanguage(null, ['fr-FR', 'ES-mx', 'en'])).toBe('es');
    expect(detectLanguage(null, ['en-GB'])).toBe('en');
  });

  it('ignores invalid stored values and falls back to English', () => {
    expect(detectLanguage('klingon', [])).toBe('en');
    expect(detectLanguage(null, ['de', 'fr'])).toBe('en');
  });
});
