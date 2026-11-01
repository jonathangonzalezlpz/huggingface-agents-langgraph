import { BrainCircuit, Download, Flag, LogIn, Search, ShieldCheck, Shapes } from 'lucide-react';
import { useCallback } from 'react';
import type { ComponentType } from 'react';

import { loadLibrary } from '../../application/loadLibrary';
import { groupComponents, shortHash } from '../../domain/catalog';
import type { Architecture, Category, ComponentInfo } from '../../domain/types';
import { isMessageKey } from '../../i18n';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';

const CATEGORY_STYLE: Record<
  Category,
  { Icon: ComponentType<{ className?: string }>; text: string }
> = {
  input: { Icon: LogIn, text: 'text-cat-input' },
  acquisition: { Icon: Download, text: 'text-cat-acquisition' },
  research: { Icon: Search, text: 'text-cat-research' },
  reasoning: { Icon: BrainCircuit, text: 'text-cat-reasoning' },
  output: { Icon: Flag, text: 'text-cat-output' },
  other: { Icon: Shapes, text: 'text-cat-other' },
};

function ArchitectureCard({ architecture }: { architecture: Architecture }) {
  const { t, tp } = useI18n();
  const { validation } = architecture;
  return (
    <li className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-mono text-base font-semibold">{architecture.architectureId}</h3>
          <p className="mt-1 text-sm text-fg-muted">
            {architecture.version === null
              ? t('builder.builtin')
              : t('builder.version', { version: architecture.version })}
            {' · '}
            <span className="font-mono">{shortHash(architecture.contentSha256)}</span>
            {' · '}
            {tp('builder.components', architecture.definition.nodes.length)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {architecture.readOnly && (
            <StatusBadge tone="neutral">{t('builder.readOnly')}</StatusBadge>
          )}
          <StatusBadge tone={validation.isValid ? 'success' : 'error'}>
            {validation.isValid ? t('builder.validation.valid') : t('builder.validation.invalid')}
          </StatusBadge>
        </div>
      </div>
      <p className="mt-3 text-sm text-fg-muted">
        {tp('diagnostics.errors', validation.counts.error)}
        {' · '}
        {tp('diagnostics.warnings', validation.counts.warning)}
        {' · '}
        {tp('diagnostics.infos', validation.counts.info)}
      </p>
    </li>
  );
}

function Library() {
  const { architectures } = useServices();
  const { t } = useI18n();
  const load = useCallback(() => loadLibrary(architectures), [architectures]);
  const state = useAsyncData(load);

  return (
    <section aria-labelledby="library-heading" className="mb-12">
      <h2 id="library-heading" className="mb-4 text-lg font-semibold">
        {t('builder.library')}
      </h2>
      {state.status === 'loading' && <p className="text-fg-muted">{t('common.loading')}</p>}
      {state.status === 'error' && <ErrorNotice error={state.error} onRetry={state.reload} />}
      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <p className="text-fg-muted">{t('builder.library.empty')}</p>
        ) : (
          <ul className="space-y-3">
            {state.data.map((architecture) => (
              <ArchitectureCard key={architecture.id} architecture={architecture} />
            ))}
          </ul>
        ))}
    </section>
  );
}

function CatalogOverview() {
  const { catalog } = useServices();
  const { t } = useI18n();
  const load = useCallback(() => catalog.getCatalog(), [catalog]);
  const describeComponent = (component: ComponentInfo) => {
    const key = `component.${component.implementationId}`;
    return isMessageKey(key) ? t(key) : component.description;
  };
  const state = useAsyncData(load);

  return (
    <section aria-labelledby="catalog-heading">
      <h2 id="catalog-heading" className="text-lg font-semibold">
        {t('builder.catalog')}
      </h2>
      <p className="mt-1 mb-4 text-sm text-fg-muted">{t('builder.catalog.hint')}</p>
      {state.status === 'loading' && <p className="text-fg-muted">{t('common.loading')}</p>}
      {state.status === 'error' && <ErrorNotice error={state.error} onRetry={state.reload} />}
      {state.status === 'success' && (
        <div className="grid gap-4 md:grid-cols-2">
          {groupComponents(state.data).map(({ category, components }) => {
            const { Icon, text } = CATEGORY_STYLE[category];
            return (
              <section
                key={category}
                aria-labelledby={`category-${category}`}
                className="rounded-xl border border-line bg-surface p-5"
              >
                <h3
                  id={`category-${category}`}
                  className={`mb-3 flex items-center gap-2 font-semibold ${text}`}
                >
                  <Icon aria-hidden="true" className="size-4" />
                  {t(`category.${category}`)}
                </h3>
                <ul className="space-y-3">
                  {components.map((component) => (
                    <li key={component.implementationId}>
                      <p className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-medium">
                          {component.implementationId}
                        </span>
                        {component.recoverErrors && (
                          <span className="inline-flex items-center gap-1 text-xs text-fg-muted">
                            <ShieldCheck aria-hidden="true" className="size-3.5" />
                            {t('builder.recoversErrors')}
                          </span>
                        )}
                      </p>
                      <p className="text-sm text-fg-muted">{describeComponent(component)}</p>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function BuilderPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t('builder.title')} description={t('builder.description')} />
      <Library />
      <CatalogOverview />
      <p className="mt-10 rounded-xl border border-dashed border-line-strong p-4 text-sm text-fg-muted">
        {t('builder.coming')}
      </p>
    </>
  );
}
