import * as ToggleGroup from '@radix-ui/react-toggle-group';
import { Monitor, Moon, Sun } from 'lucide-react';
import type { ComponentType } from 'react';

import { useI18n } from '../../i18n/I18nProvider';
import { LANGUAGES, type Language, type MessageKey } from '../../i18n';
import { useTheme, type ThemePreference } from '../../theme/ThemeProvider';

const ITEM_CLASSES =
  'inline-flex size-8 items-center justify-center rounded-md text-sm font-medium text-fg-muted ' +
  'hover:bg-muted data-[state=on]:bg-accent-soft data-[state=on]:text-accent-fg';

const THEMES: {
  value: ThemePreference;
  label: MessageKey;
  Icon: ComponentType<{ className?: string }>;
}[] = [
  { value: 'system', label: 'controls.theme.system', Icon: Monitor },
  { value: 'light', label: 'controls.theme.light', Icon: Sun },
  { value: 'dark', label: 'controls.theme.dark', Icon: Moon },
];

const LANGUAGE_NAMES: Record<Language, string> = { es: 'Español', en: 'English' };

export function ThemeToggle() {
  const { t } = useI18n();
  const { preference, setPreference } = useTheme();
  return (
    <ToggleGroup.Root
      type="single"
      value={preference}
      onValueChange={(value) => {
        if (value) setPreference(value as ThemePreference);
      }}
      aria-label={t('controls.theme')}
      className="flex gap-1 rounded-lg border border-line bg-surface p-1"
    >
      {THEMES.map(({ value, label, Icon }) => (
        <ToggleGroup.Item
          key={value}
          value={value}
          aria-label={t(label)}
          title={t(label)}
          className={ITEM_CLASSES}
        >
          <Icon aria-hidden="true" className="size-4" />
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}

export function LanguageToggle() {
  const { t, language, setLanguage } = useI18n();
  return (
    <ToggleGroup.Root
      type="single"
      value={language}
      onValueChange={(value) => {
        if (value) setLanguage(value as Language);
      }}
      aria-label={t('controls.language')}
      className="flex gap-1 rounded-lg border border-line bg-surface p-1"
    >
      {LANGUAGES.map((code) => (
        <ToggleGroup.Item
          key={code}
          value={code}
          aria-label={LANGUAGE_NAMES[code]}
          title={LANGUAGE_NAMES[code]}
          lang={code}
          className={ITEM_CLASSES}
        >
          {code.toUpperCase()}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
