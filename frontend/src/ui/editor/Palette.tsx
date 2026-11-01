import { useId, useState } from 'react';

import { groupComponents } from '../../domain/catalog';
import type { Catalog } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { CATEGORY_STYLE } from '../components/categoryStyle';
import { useComponentDescription } from '../components/componentText';
import { filterComponents } from './componentSearch';

export const PALETTE_MIME = 'application/x-studio-component';

export function Palette({
  catalog,
  disabled,
  onAdd,
}: {
  catalog: Catalog;
  disabled: boolean;
  onAdd: (implementationId: string) => void;
}) {
  const { t } = useI18n();
  const describe = useComponentDescription();
  const [query, setQuery] = useState('');
  const searchId = useId();

  const visible = { ...catalog, components: filterComponents(catalog.components, query, describe) };
  const groups = groupComponents(visible);

  return (
    <section aria-labelledby={`${searchId}-title`} className="flex h-full min-h-0 flex-col">
      <h2 id={`${searchId}-title`} className="px-3 pt-3 text-sm font-semibold">
        {t('editor.palette')}
      </h2>
      <div className="p-3">
        <label htmlFor={searchId} className="sr-only">
          {t('editor.palette.search')}
        </label>
        <input
          id={searchId}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('editor.palette.search')}
          className="min-h-9 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm"
        />
        <p className="mt-2 text-xs text-fg-muted">{t('editor.palette.hint')}</p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {groups.length === 0 && (
          <p className="text-sm text-fg-muted">{t('editor.palette.empty')}</p>
        )}
        {groups.map(({ category, components }) => {
          const { Icon, text } = CATEGORY_STYLE[category];
          return (
            <section key={category} className="mb-4">
              <h3 className={`mb-1.5 flex items-center gap-1.5 text-xs font-semibold ${text}`}>
                <Icon aria-hidden="true" className="size-3.5" />
                {t(`category.${category}`)}
              </h3>
              <ul className="space-y-1.5">
                {components.map((component) => (
                  <li key={component.implementationId}>
                    <button
                      type="button"
                      disabled={disabled}
                      draggable={!disabled}
                      onDragStart={(event) => {
                        event.dataTransfer.setData(PALETTE_MIME, component.implementationId);
                        event.dataTransfer.effectAllowed = 'copy';
                      }}
                      onClick={() => onAdd(component.implementationId)}
                      className="block w-full rounded-lg border border-line bg-surface px-2.5 py-2 text-left hover:border-accent hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <span className="block font-mono text-xs font-medium">
                        {component.implementationId}
                      </span>
                      <span className="mt-0.5 block text-xs text-fg-muted">
                        {describe(component)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </section>
  );
}
