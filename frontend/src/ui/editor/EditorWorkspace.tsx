import { ReactFlowProvider } from '@xyflow/react';
import { X } from 'lucide-react';
import { useEffect, useMemo, useReducer, useRef, useState } from 'react';

import {
  addNode,
  applyLayout,
  clearDecision,
  connect,
  connectBranch,
  disconnect,
  disconnectBranch,
  moveNodes,
  removeNode,
  renameNode,
  setDecision,
  setInitial,
  uniqueNodeId,
} from '../../domain/editor/commands';
import { toDefinition } from '../../domain/editor/convert';
import { type EditorDocument, type EditorGraph, type Point } from '../../domain/editor/model';
import { StudioError } from '../../domain/errors';
import type { Catalog, ValidationReport } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { useServices } from '../services';
import { computeLayout } from './autoLayout';
import { DiagnosticsPanel, type ValidationView } from './DiagnosticsPanel';
import { AddComponentDialog, ConnectDialog } from './dialogs';
import { EditorCanvas, type CanvasApi } from './EditorCanvas';
import { editorReducer, initialState, type EditorAction } from './editorState';
import { Inspector, type InspectorActions } from './Inspector';
import { Palette } from './Palette';
import { rejectionText } from './rejectionText';
import { Toolbar } from './Toolbar';

const DRAFT_SAVE_DELAY_MS = 400;
const LAYOUT_SAVE_DELAY_MS = 600;
const NEW_NODE_STAGGER = 28;

export interface WorkspaceProps {
  initialDocument: EditorDocument;
  catalog: Catalog;
  /** A read-only version: its structure cannot change, but its layout can. */
  readOnly: boolean;
  /** Persist the whole document as this local draft. */
  draftId?: string;
  /** Persist only the layout, for the saved or built-in version with this id. */
  layoutKey?: string;
  /** The stored validation of a saved version, shown until the graph is validated again. */
  initialValidation?: ValidationReport;
  onDuplicate: (document: EditorDocument) => void;
}

type Apply = Extract<EditorAction, { type: 'apply' }>;
type Validated = { view: ValidationView; graph: EditorGraph | null };

function Workspace({
  initialDocument,
  catalog,
  readOnly,
  draftId,
  layoutKey,
  initialValidation,
  onDuplicate,
}: WorkspaceProps) {
  const { t } = useI18n();
  const services = useServices();
  const [state, dispatch] = useReducer(editorReducer, initialDocument, initialState);
  const doc = state.history.present;
  const canvasApi = useRef<CanvasApi | null>(null);

  const [selection, setSelection] = useState<string[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const [connectTo, setConnectTo] = useState<{ nodeId: string; branch: string | null } | null>(
    null,
  );
  const [validated, setValidated] = useState<Validated>(
    initialValidation
      ? { view: { status: 'done', report: initialValidation }, graph: initialDocument.graph }
      : { view: { status: 'idle' }, graph: null },
  );

  const nodeIds = useMemo(() => doc.graph.nodes.map((node) => node.id), [doc.graph.nodes]);
  const selected = useMemo(
    () => selection.filter((id) => nodeIds.includes(id)),
    [selection, nodeIds],
  );
  const primary = selected.length === 1 ? (selected[0] ?? null) : null;

  const stale = validated.view.status === 'done' && validated.graph !== doc.graph;
  const diagnostics = useMemo(
    () => (validated.view.status === 'done' && !stale ? validated.view.report.diagnostics : []),
    [validated.view, stale],
  );

  /** Run a command; `onSuccess` receives the resulting document when it was accepted. */
  const execute = (
    run: Apply['run'],
    announce?: Apply['announce'],
    onSuccess?: (next: EditorDocument) => void,
  ) => {
    const result = run(doc);
    dispatch(announce ? { type: 'apply', run, announce } : { type: 'apply', run });
    if (result.ok) onSuccess?.(result.doc);
  };

  const addComponent = (implementationId: string, position?: Point) => {
    const offset = (doc.graph.nodes.length % 6) * NEW_NODE_STAGGER;
    const at = position ?? {
      x: Math.round((canvasApi.current?.centerPosition().x ?? 0) + offset - 120),
      y: Math.round((canvasApi.current?.centerPosition().y ?? 0) + offset - 40),
    };
    const newId = uniqueNodeId(doc.graph, implementationId);
    execute(
      (current) => addNode(current, catalog, implementationId, at),
      () => ({ key: 'editor.announce.added', params: { id: newId } }),
      () => setSelection([newId]),
    );
  };

  const runLayout = () => {
    const positions = computeLayout(doc.graph);
    execute(
      (current) => applyLayout(current, positions),
      () => ({ key: 'editor.announce.layout' }),
      () => requestAnimationFrame(() => canvasApi.current?.fit()),
    );
  };

  const validate = async () => {
    const graph = doc.graph;
    setValidated({ view: { status: 'running' }, graph: null });
    try {
      const report = await services.validation.validate(toDefinition(graph));
      setValidated({ view: { status: 'done', report }, graph });
    } catch (error) {
      const unavailable = error instanceof StudioError && error.kind === 'unavailable';
      setValidated({ view: { status: unavailable ? 'unavailable' : 'failed' }, graph: null });
    }
  };

  const goToNode = (id: string) => {
    setSelection([id]);
    canvasApi.current?.focusNode(id);
  };

  const inspectorActions: InspectorActions = {
    rename: (id, newId) =>
      execute(
        (current) => renameNode(current, id, newId),
        () => ({ key: 'editor.announce.renamed', params: { id, newId } }),
        () => setSelection([newId]),
      ),
    setEntry: (id) =>
      execute(
        (current) => setInitial(current, id),
        () => ({ key: 'editor.announce.entry', params: { id } }),
      ),
    remove: (id) =>
      execute(
        (current) => removeNode(current, id),
        () => ({ key: 'editor.announce.removed', params: { id } }),
        () => setSelection([]),
      ),
    openConnect: (nodeId, branch) => setConnectTo({ nodeId, branch }),
    disconnect: (nodeId, branch) =>
      execute(
        (current) =>
          branch ? disconnectBranch(current, nodeId, branch) : disconnect(current, nodeId),
        () => ({ key: 'editor.announce.disconnected', params: { source: nodeId } }),
      ),
    setDecision: (nodeId, strategy) =>
      execute(
        (current) =>
          strategy === ''
            ? clearDecision(current, nodeId)
            : setDecision(current, catalog, nodeId, strategy),
        () => ({ key: 'editor.announce.decision', params: { id: nodeId, strategy } }),
      ),
  };

  // Keyboard shortcuts. The latest handler is kept in a ref so the listener is attached once.
  const shortcut = useRef<(event: KeyboardEvent) => void>(() => undefined);
  useEffect(() => {
    shortcut.current = (event) => {
      const target = event.target as HTMLElement | null;
      const typing =
        !!target && (target.matches('input, textarea, select') || target.isContentEditable);
      const mod = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();
      if (mod && key === 'k') {
        event.preventDefault();
        if (!readOnly) setAddOpen(true);
        return;
      }
      if (typing || addOpen || connectTo) return;
      if (mod && key === 'z') {
        event.preventDefault();
        dispatch({ type: event.shiftKey ? 'redo' : 'undo' });
      } else if (mod && key === 'y') {
        event.preventDefault();
        dispatch({ type: 'redo' });
      } else if (!mod && key === 'f') {
        canvasApi.current?.fit();
      } else if (!mod && key === 'l') {
        runLayout();
      }
    };
  });
  useEffect(() => {
    const listener = (event: KeyboardEvent) => shortcut.current(event);
    document.addEventListener('keydown', listener);
    return () => document.removeEventListener('keydown', listener);
  }, []);

  // Persistence: drafts keep everything, saved versions keep only where nodes sit.
  const latest = useRef(doc);
  useEffect(() => {
    latest.current = doc;
  }, [doc]);

  useEffect(() => {
    if (!draftId || doc === initialDocument) return;
    const timer = setTimeout(() => services.drafts.save(draftId, doc), DRAFT_SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [doc, draftId, initialDocument, services.drafts]);

  useEffect(() => {
    if (!draftId) return;
    return () => {
      if (latest.current !== initialDocument) services.drafts.save(draftId, latest.current);
    };
  }, [draftId, initialDocument, services.drafts]);

  useEffect(() => {
    if (!layoutKey || doc.layout === initialDocument.layout) return;
    const timer = setTimeout(() => {
      services.layouts.save(layoutKey, doc.layout).catch(() => undefined);
    }, LAYOUT_SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [doc.layout, layoutKey, initialDocument.layout, services.layouts]);

  const announcement = state.announcement
    ? t(state.announcement.key, state.announcement.params)
    : '';

  return (
    <div className="flex h-screen min-h-0 flex-col">
      <Toolbar
        title={doc.graph.architectureId}
        draft={draftId !== undefined}
        readOnly={readOnly}
        canUndo={state.history.past.length > 0}
        canRedo={state.history.future.length > 0}
        validating={validated.view.status === 'running'}
        onUndo={() => dispatch({ type: 'undo' })}
        onRedo={() => dispatch({ type: 'redo' })}
        onAdd={() => setAddOpen(true)}
        onLayout={runLayout}
        onFit={() => canvasApi.current?.fit()}
        onValidate={() => void validate()}
        onDuplicate={() => onDuplicate(doc)}
      />
      {readOnly && (
        <p className="border-b border-line bg-muted px-4 py-1.5 text-xs text-fg-muted">
          {t('editor.readOnlyHint')}
        </p>
      )}
      {state.notice && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 border-b border-line bg-warning-soft px-4 py-1.5 text-sm text-warning"
        >
          <span>{rejectionText(t, state.notice)}</span>
          <button
            type="button"
            onClick={() => dispatch({ type: 'dismissNotice' })}
            aria-label={t('editor.cancel')}
            className="inline-flex size-7 items-center justify-center rounded-md hover:bg-surface/50"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
      )}

      <div
        className={`grid min-h-0 flex-1 grid-cols-1 ${
          readOnly
            ? 'lg:grid-cols-[minmax(0,1fr)_19rem]'
            : 'lg:grid-cols-[16rem_minmax(0,1fr)_19rem]'
        }`}
      >
        {!readOnly && (
          <div className="hidden min-h-0 border-r border-line bg-surface lg:block">
            <Palette catalog={catalog} disabled={false} onAdd={(id) => addComponent(id)} />
          </div>
        )}
        <div className="relative min-h-[26rem] min-w-0">
          <EditorCanvas
            doc={doc}
            catalog={catalog}
            diagnostics={diagnostics}
            readOnly={readOnly}
            selectedIds={selected}
            onSelect={setSelection}
            onApply={dispatch}
            onMove={(positions) => execute((current) => moveNodes(current, positions))}
            onAddComponent={addComponent}
            apiRef={canvasApi}
          />
        </div>
        <div className="min-h-0 overflow-y-auto border-l border-line bg-surface">
          <Inspector
            doc={doc}
            catalog={catalog}
            selectedId={primary}
            readOnly={readOnly}
            actions={inspectorActions}
          />
        </div>
      </div>

      <div className="border-t border-line bg-surface">
        <DiagnosticsPanel view={validated.view} stale={stale} onGoto={goToNode} />
      </div>

      <AddComponentDialog
        open={addOpen}
        catalog={catalog}
        onClose={() => setAddOpen(false)}
        onAdd={(id) => addComponent(id)}
      />
      <ConnectDialog
        node={connectTo ? (doc.graph.nodes.find((n) => n.id === connectTo.nodeId) ?? null) : null}
        nodeIds={nodeIds}
        initialBranch={connectTo?.branch ?? null}
        onClose={() => setConnectTo(null)}
        onConfirm={(target, branch) => {
          if (!connectTo) return;
          const { nodeId } = connectTo;
          execute(
            (current) =>
              branch
                ? connectBranch(current, nodeId, branch, target)
                : connect(current, nodeId, target),
            () => ({ key: 'editor.announce.connected', params: { source: nodeId, target } }),
          );
          setConnectTo(null);
        }}
      />
      <div role="status" aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </div>
  );
}

export function EditorWorkspace(props: WorkspaceProps) {
  return (
    <ReactFlowProvider>
      <Workspace {...props} />
    </ReactFlowProvider>
  );
}
