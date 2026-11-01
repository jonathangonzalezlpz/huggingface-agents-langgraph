import { Plus, ShieldCheck, Trash2 } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { loadLibrary } from '../../application/loadLibrary';
import { groupComponents, shortHash } from '../../domain/catalog';
import type { Architecture } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { CATEGORY_STYLE } from '../components/categoryStyle';
import { useComponentDescription } from '../components/componentText';
import { ErrorNotice } from '../components/ErrorNotice';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { useAsyncData } from '../hooks/useAsyncData';
import { buildDraft, saveNewDraft, type DraftKind } from '../editor/drafts';
import { useServices } from '../services';

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
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted">
          {tp('diagnostics.errors', validation.counts.error)}
          {' · '}
          {tp('diagnostics.warnings', validation.counts.warning)}
          {' · '}
          {tp('diagnostics.infos', validation.counts.info)}
        </p>
        <Link
          to={`/builder/architecture/${encodeURIComponent(architecture.id)}`}
          aria-label={`${t('builder.open')} ${architecture.architectureId}`}
          className="inline-flex min-h-9 items-center rounded-lg border border-line-strong bg-surface px-3 text-sm font-medium hover:bg-muted"
        >
          {t('builder.open')}
        </Link>
      </div>
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

const NEW_DRAFT_KINDS: {
  kind: DraftKind;
  label: 'builder.new.blank' | 'builder.new.linear' | 'builder.new.copy';
}[] = [
  { kind: 'blank', label: 'builder.new.blank' },
  { kind: 'linear', label: 'builder.new.linear' },
  { kind: 'copy', label: 'builder.new.copy' },
];

function Drafts() {
  const services = useServices();
  const { t, tp } = useI18n();
  const navigate = useNavigate();
  const [revision, setRevision] = useState(0);
  const [failure, setFailure] = useState<unknown>(null);
  // `revision` only exists to re-read the drafts after one is deleted.
  const drafts = revision >= 0 ? services.drafts.list() : [];

  const create = async (kind: DraftKind) => {
    try {
      const [catalog, library] = await Promise.all([
        services.catalog.getCatalog(),
        services.architectures.list(),
      ]);
      const builtin = library.find((item) => item.readOnly);
      const source =
        kind === 'copy' && builtin ? await services.architectures.get(builtin.id) : undefined;
      const taken = services.drafts.list().map((draft) => draft.architectureId);
      const doc = buildDraft(kind, catalog, taken, source);
      navigate(`/builder/draft/${saveNewDraft(services, doc)}`);
    } catch (error) {
      setFailure(error);
    }
  };

  return (
    <section aria-labelledby="drafts-heading" className="mb-12">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
        <h2 id="drafts-heading" className="text-lg font-semibold">
          {t('builder.drafts')}
        </h2>
        <div
          role="group"
          aria-label={t('builder.new')}
          className="flex flex-wrap items-center gap-2"
        >
          <span className="inline-flex items-center gap-1 text-sm font-medium">
            <Plus aria-hidden="true" className="size-4" />
            {t('builder.new')}
          </span>
          {NEW_DRAFT_KINDS.map(({ kind, label }) => (
            <button
              key={kind}
              type="button"
              onClick={() => void create(kind)}
              className="min-h-9 rounded-lg border border-line-strong bg-surface px-3 text-sm font-medium hover:bg-muted"
            >
              {t(label)}
            </button>
          ))}
        </div>
      </div>
      <p className="mb-4 text-sm text-fg-muted">{t('builder.drafts.hint')}</p>
      {failure !== null && <ErrorNotice error={failure} onRetry={() => setFailure(null)} />}
      {drafts.length === 0 ? (
        <p className="text-fg-muted">{t('builder.drafts.empty')}</p>
      ) : (
        <ul className="space-y-3">
          {drafts.map((draft) => (
            <li
              key={draft.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface p-4"
            >
              <div>
                <p className="font-mono text-base font-semibold">{draft.architectureId}</p>
                <p className="text-sm text-fg-muted">
                  {tp('builder.drafts.nodes', draft.nodeCount)}
                </p>
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/builder/draft/${encodeURIComponent(draft.id)}`}
                  aria-label={`${t('builder.open')} ${draft.architectureId}`}
                  className="inline-flex min-h-9 items-center rounded-lg border border-line-strong bg-surface px-3 text-sm font-medium hover:bg-muted"
                >
                  {t('builder.open')}
                </Link>
                <button
                  type="button"
                  aria-label={`${t('builder.drafts.delete')} ${draft.architectureId}`}
                  title={t('builder.drafts.delete')}
                  onClick={() => {
                    services.drafts.remove(draft.id);
                    setRevision((current) => current + 1);
                  }}
                  className="inline-flex size-9 items-center justify-center rounded-lg border border-line-strong text-error hover:bg-error-soft"
                >
                  <Trash2 aria-hidden="true" className="size-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CatalogOverview() {
  const { catalog } = useServices();
  const { t } = useI18n();
  const load = useCallback(() => catalog.getCatalog(), [catalog]);
  const describeComponent = useComponentDescription();
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
      <Drafts />
      <CatalogOverview />
    </>
  );
}
