import { en } from './messages.en';
import { es, type MessageKey } from './messages.es';

export type Language = 'es' | 'en';
export const LANGUAGES: readonly Language[] = ['es', 'en'];
export const LANGUAGE_STORAGE_KEY = 'studio.language';

export type { MessageKey };
/** Keys that have `.one` and `.other` variants, addressed by their common prefix. */
export type PluralKey = MessageKey extends infer K
  ? K extends `${infer Base}.one`
    ? Base
    : never
  : never;

export type Params = Record<string, string | number>;

const catalogs: Record<Language, Record<MessageKey, string>> = { es, en };

function asLanguage(value: string | null | undefined): Language | null {
  const base = value?.toLowerCase().split('-')[0];
  return LANGUAGES.find((language) => language === base) ?? null;
}

/** A stored choice wins; otherwise the first supported browser language; else English. */
export function detectLanguage(
  stored: string | null,
  browserLanguages: readonly string[],
): Language {
  const explicit = asLanguage(stored);
  if (explicit) return explicit;
  for (const candidate of browserLanguages) {
    const supported = asLanguage(candidate);
    if (supported) return supported;
  }
  return 'en';
}

export function translate(language: Language, key: MessageKey, params: Params = {}): string {
  return catalogs[language][key].replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    name in params ? String(params[name]) : placeholder,
  );
}

export function translatePlural(
  language: Language,
  base: PluralKey,
  count: number,
  params: Params = {},
): string {
  const category = new Intl.PluralRules(language).select(count) === 'one' ? 'one' : 'other';
  return translate(language, `${base}.${category}` as MessageKey, { ...params, count });
}

export function isMessageKey(key: string): key is MessageKey {
  return key in es;
}

export function messageKeys(language: Language): string[] {
  return Object.keys(catalogs[language]);
}
