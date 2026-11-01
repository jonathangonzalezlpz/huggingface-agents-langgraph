import { useCallback, useMemo } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { StudioError } from '../../domain/errors';
import { documentFromArchitecture } from '../../domain/editor/templates';
import type { EditorDocument } from '../../domain/editor/model';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import { useAsyncData } from '../hooks/useAsyncData';
import { useServices } from '../services';
import { computeLayout } from './autoLayout';
import { saveNewDraft, uniqueArchitectureId } from './drafts';
import { EditorWorkspace } from './EditorWorkspace';

function Message({ children }: { children: string }) {
  const { t } = useI18n();
  return (
    <div className="p-8">
      <p className="mb-3 text-fg-muted">{children}</p>
      <Link to="/builder" className="text-accent-fg underline underline-offset-2">
        {t('editor.back')}
      </Link>
    </div>
  );
}

function useDuplicate() {
  const services = useServices();
  const navigate = useNavigate();
  return (doc: EditorDocument) => {
    const taken = services.drafts.list().map((draft) => draft.architectureId);
    const copy: EditorDocument = {
      ...doc,
      graph: {
        ...doc.graph,
        architectureId: uniqueArchitectureId(`${doc.graph.architectureId}_copy`, taken),
      },
    };
    navigate(`/builder/draft/${saveNewDraft(services, copy)}`);
  };
}

/** A saved or built-in version: structure is read-only, layout is kept. */
export function ArchitectureEditorPage() {
  const { id = '' } = useParams();
  const { t } = useI18n();
  const { architectures, catalog, layouts } = useServices();
  const duplicate = useDuplicate();

  const load = useCallback(async () => {
    const [architecture, components, stored] = await Promise.all([
      architectures.get(id),
      catalog.getCatalog(),
      layouts.get(id).catch(() => ({})),
    ]);
    return { architecture, components, stored };
  }, [architectures, catalog, layouts, id]);
  const state = useAsyncData(load);

  const initial = useMemo(() => {
    if (state.status !== 'success') return null;
    const { architecture, components, stored } = state.data;
    const base = documentFromArchitecture(
      architecture,
      components,
      architecture.architectureId,
      stored,
    );
    const hasLayout = base.graph.nodes.every((node) => base.layout[node.id]);
    return hasLayout ? base : { ...base, layout: { ...computeLayout(base.graph), ...base.layout } };
  }, [state]);

  if (state.status === 'loading') return <Message>{t('common.loading')}</Message>;
  if (state.status === 'error') {
    if (state.error instanceof StudioError && state.error.status === 404) {
      return <Message>{t('editor.notFound')}</Message>;
    }
    return (
      <div className="p-8">
        <ErrorNotice error={state.error} onRetry={state.reload} />
      </div>
    );
  }
  if (!initial) return null;

  return (
    <EditorWorkspace
      key={id}
      initialDocument={initial}
      catalog={state.data.components}
      readOnly
      layoutKey={id}
      initialValidation={state.data.architecture.validation}
      onDuplicate={duplicate}
    />
  );
}

/** A local draft: fully editable. */
export function DraftEditorPage() {
  const { id = '' } = useParams();
  const { t } = useI18n();
  const services = useServices();
  const duplicate = useDuplicate();
  const draft = useMemo(() => services.drafts.load(id), [services.drafts, id]);
  const load = useCallback(() => services.catalog.getCatalog(), [services.catalog]);
  const state = useAsyncData(load);

  if (!draft) return <Message>{t('editor.notFound')}</Message>;
  if (state.status === 'loading') return <Message>{t('common.loading')}</Message>;
  if (state.status === 'error') {
    return (
      <div className="p-8">
        <ErrorNotice error={state.error} onRetry={state.reload} />
      </div>
    );
  }

  return (
    <EditorWorkspace
      key={id}
      initialDocument={draft}
      catalog={state.data}
      readOnly={false}
      draftId={id}
      onDuplicate={duplicate}
    />
  );
}
