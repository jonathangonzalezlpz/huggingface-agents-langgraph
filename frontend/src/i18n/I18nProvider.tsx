import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import {
  detectLanguage,
  LANGUAGE_STORAGE_KEY,
  translate,
  translatePlural,
  type Language,
  type MessageKey,
  type Params,
  type PluralKey,
} from './index';

interface I18nValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: MessageKey, params?: Params) => string;
  tp: (base: PluralKey, count: number, params?: Params) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function initialLanguage(): Language {
  return detectLanguage(localStorage.getItem(LANGUAGE_STORAGE_KEY), navigator.languages);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const setLanguage = useCallback((next: Language) => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, next);
    setLanguageState(next);
  }, []);

  const value = useMemo<I18nValue>(
    () => ({
      language,
      setLanguage,
      t: (key, params) => translate(language, key, params),
      tp: (base, count, params) => translatePlural(language, base, count, params),
    }),
    [language, setLanguage],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n must be used inside I18nProvider');
  return value;
}
