import { ReactFlowProvider } from '@xyflow/react';
import { X } from 'lucide-react';
import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

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
  renameArchitecture,
  renameNode,
  setDecision,
  setDescription,
  setInitial,
  uniqueNodeId,
} from '../../domain/editor/commands';
import { toDefinition, unexportableDecisions } from '../../domain/editor/convert';
import { type EditorDocument, type EditorGraph, type Point } from '../../domain/editor/model';
import { StudioError } from '../../domain/errors';
import type { Catalog, ValidationReport } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import type { SavedMarker } from '../../ports';
import { useServices } from '../services';
import { computeLayout } from './autoLayout';
import { DiagnosticsPanel, type ValidationView } from './DiagnosticsPanel';
import { AddComponentDialog, ConnectDialog } from './dialogs';
import { EditorCanvas, type CanvasApi } from './EditorCanvas';
import { editorReducer, initialState, type EditorAction } from './editorState';
import { Inspector, type InspectorActions } from './Inspector';
import type { AvailabilityView } from './InspectorFields';
import { Palette } from './Palette';
import { rejectionText } from './rejectionText';
import { Toolbar } from './Toolbar';

const DRAFT_SAVE_DELAY_MS = 400;
const LAYOUT_SAVE_DELAY_MS = 600;
const VALIDATION_DELAY_MS = 600;
const NEW_NODE_STAGGER = 28;

export interface WorkspaceProps {
  initialDocument: EditorDocument;
  catalog: Catalog;
  /** A read-only version: its structure cannot change, but its layout can. */
  readOnly: boolean;
  /** Persist the whole document as this local draft; also enables saving versions. */
  draftId?: string;
  /** The stored version a read-only view can run. */
  runVersionId?: string;
  /** Persist only the layout, for the saved or built-in version with this id. */
  layoutKey?: string;
  /** The stored validation of a saved version, shown until the graph is validated again. */
  initialValidation?: ValidationReport;
  /** What the button of a read-only version does: edit it, or duplicate it under a new name. */
  editLabel?: 'editor.edit' | 'editor.duplicate';
  onEdit: (document: EditorDocument) => void;
}

type Apply = Extract<EditorAction, { type: 'apply' }>;
type Validated = { view: ValidationView; graph: EditorGraph | null };
type Notice = { tone: 'success' | 'warning' | 'error'; text: string } | null;

const NOTICE_TONE = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  error: 'bg-error-soft text-error',
} as const;

function Workspace({
  initialDocument,
  catalog,
  readOnly,
  draftId,
  runVersionId,
  layoutKey,
  initialValidation,
  editLabel = 'editor.duplicate',
  onEdit,
}: WorkspaceProps) {
  const { t, tp } = useI18n();
  const services = useServices();
  const navigate = useNavigate();
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
  const [validating, setValidating] = useState(false);
  const [liveValidation, setLiveValidation] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveNotice, setSaveNotice] = useState<Notice>(null);
  const [marker, setMarker] = useState<SavedMarker | null>(() =>
    draftId ? services.drafts.savedMarker(draftId) : null,
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

  const currentJson = useMemo(() => JSON.stringify(toDefinition(doc.graph)), [doc.graph]);
  const saveState: 'saved' | 'unsaved' | null = draftId
    ? marker && marker.definitionJson === currentJson
      ? 'saved'
      : 'unsaved'
    : null;

  const availability: AvailabilityView = (() => {
    const { view } = validated;
    if (view.status === 'unavailable') return { status: 'unavailable' };
    if (view.status !== 'done') return { status: 'pending' };
    if (stale) return { status: 'stale' };
    return { status: 'ready', node: primary ? (view.report.availability[primary] ?? null) : null };
  })();

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

  // Validation: a response only counts if no newer request started after it.
  const requestSerial = useRef(0);
  const runValidation = async (graph: EditorGraph) => {
    const serial = ++requestSerial.current;
    setValidating(true);
    try {
      const report = await services.validation.validate(toDefinition(graph));
      if (serial !== requestSerial.current) return;
      setValidated({ view: { status: 'done', report }, graph });
    } catch (error) {
      if (serial !== requestSerial.current) return;
      const unavailable = error instanceof StudioError && error.kind === 'unavailable';
      if (unavailable) setLiveValidation(false);
      setValidated({ view: { status: unavailable ? 'unavailable' : 'failed' }, graph: null });
    }
    setValidating(false);
  };

  const validateLatest = useRef(runValidation);
  useEffect(() => {
    validateLatest.current = runValidation;
  });
  useEffect(() => {
    if (readOnly || !liveValidation || doc.graph.nodes.length === 0) return;
    const timer = setTimeout(() => void validateLatest.current(doc.graph), VALIDATION_DELAY_MS);
    return () => clearTimeout(timer);
  }, [doc.graph, readOnly, liveValidation]);

  /** Save the draft as a version. Resolves to its id only when it is clean enough to run. */
  const saveVersion = async (): Promise<string | null> => {
    if (!draftId) return null;
    if (doc.graph.nodes.length === 0) {
      setSaveNotice({ tone: 'error', text: t('editor.save.empty') });
      return null;
    }
    const snapshot = doc;
    const snapshotJson = currentJson;
    setSaving(true);
    setSaveNotice(null);
    try {
      const { architecture, created } = await services.architectures.save(
        toDefinition(snapshot.graph),
      );
      const saved: SavedMarker = {
        versionId: architecture.id,
        version: architecture.version ?? 0,
        definitionJson: snapshotJson,
      };
      services.drafts.save(draftId, snapshot);
      services.drafts.markSaved(draftId, saved);
      setMarker(saved);

      const parts = [
        created
          ? t('editor.save.created', { version: saved.version })
          : t('editor.save.existing', { version: saved.version }),
      ];
      const errors = architecture.validation.counts.error;
      if (errors > 0) parts.push(tp('editor.save.withErrors', errors));
      const dropped = unexportableDecisions(snapshot.graph);
      if (dropped.length > 0) parts.push(t('editor.save.dropped', { ids: dropped.join(', ') }));
      setSaveNotice({
        tone: errors > 0 || dropped.length > 0 ? 'warning' : 'success',
        text: parts.join(' '),
      });
      return errors === 0 && dropped.length === 0 ? architecture.id : null;
    } catch (error) {
      const unavailable = error instanceof StudioError && error.kind === 'unavailable';
      setSaveNotice({
        tone: 'error',
        text: t(unavailable ? 'editor.save.unavailable' : 'editor.save.failed'),
      });
      return null;
    } finally {
      setSaving(false);
    }
  };

  const live = services.mode === 'live';
  const invalidNow = validated.view.status === 'done' && !stale && !validated.view.report.isValid;
  const run: { label: 'editor.run' | 'editor.runSave'; disabled: boolean } | null = readOnly
    ? runVersionId
      ? { label: 'editor.run', disabled: !live || initialValidation?.isValid === false }
      : null
    : draftId
      ? {
          label: saveState === 'saved' ? 'editor.run' : 'editor.runSave',
          disabled: !live || saving || invalidNow,
        }
      : null;

  const startRun = async () => {
    const versionId = readOnly
      ? (runVersionId ?? null)
      : saveState === 'saved'
        ? (marker?.versionId ?? null)
        : await saveVersion();
    if (versionId) void navigate(`/runs?architecture=${encodeURIComponent(versionId)}`);
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
    setDescription: (nodeId, text) => execute((current) => setDescription(current, nodeId, text)),
    renameArchitecture: (name) => execute((current) => renameArchitecture(current, name)),
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
      if (mod && key === 's' && draftId) {
        event.preventDefault();
        void saveVersion();
      } else if (mod && key === 'z') {
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
        validating={validating}
        saveState={saveState}
        savedVersion={marker?.version ?? null}
        saving={saving}
        editLabel={editLabel}
        onUndo={() => dispatch({ type: 'undo' })}
        onRedo={() => dispatch({ type: 'redo' })}
        onAdd={() => setAddOpen(true)}
        onLayout={runLayout}
        onFit={() => canvasApi.current?.fit()}
        onValidate={() => void runValidation(doc.graph)}
        run={run}
        onSave={() => void saveVersion()}
        onRun={() => void startRun()}
        onEdit={() => onEdit(doc)}
      />
      {readOnly && (
        <p className="border-b border-line bg-muted px-4 py-1.5 text-xs text-fg-muted">
          {t(editLabel === 'editor.edit' ? 'editor.readOnlyHint.saved' : 'editor.readOnlyHint')}
        </p>
      )}
      {saveNotice && (
        <div
          role="status"
          className={`flex items-center justify-between gap-3 border-b border-line px-4 py-1.5 text-sm ${NOTICE_TONE[saveNotice.tone]}`}
        >
          <span>{saveNotice.text}</span>
          <button
            type="button"
            onClick={() => setSaveNotice(null)}
            aria-label={t('editor.cancel')}
            className="inline-flex size-7 items-center justify-center rounded-md hover:bg-surface/50"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
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
            availability={availability}
          />
        </div>
      </div>

      <div className="border-t border-line bg-surface">
        <DiagnosticsPanel
          view={validated.view}
          stale={stale}
          updating={validating}
          onGoto={goToNode}
        />
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
