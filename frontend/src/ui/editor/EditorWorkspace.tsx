import { ReactFlowProvider } from '@xyflow/react';
import { useMemo, useReducer, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  addNode,
  applyLayout,
  connect,
  connectBranch,
  moveNodes,
  uniqueNodeId,
} from '../../domain/editor/commands';
import { type EditorDocument, type Point } from '../../domain/editor/model';
import type { Catalog, ValidationReport } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { useServices } from '../services';
import { computeLayout } from './autoLayout';
import { DiagnosticsPanel } from './DiagnosticsPanel';
import { AddComponentDialog, ConnectDialog } from './dialogs';
import { EditorCanvas, type CanvasApi } from './EditorCanvas';
import { editorReducer, initialState, type EditorAction } from './editorState';
import { createInspectorActions } from './inspectorActions';
import { Inspector } from './Inspector';
import { EditorNotices } from './EditorNotices';
import { Palette } from './Palette';
import { runButtonState } from './runButton';
import { Toolbar } from './Toolbar';
import { useEditorPersistence } from './useEditorPersistence';
import { useEditorShortcuts } from './useEditorShortcuts';
import { useValidation } from './useValidation';
import { useVersionSaving } from './useVersionSaving';
import { availabilityView, hasErrorsNow, visibleDiagnostics } from './validationView';

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
  const { t } = useI18n();
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

  const { validated, validating, stale, validate } = useValidation({
    graph: doc.graph,
    initialGraph: initialDocument.graph,
    readOnly,
    initialValidation,
  });
  const { marker, saving, notice, dismissNotice, saveState, saveVersion } = useVersionSaving({
    doc,
    ...(draftId ? { draftId } : {}),
  });
  useEditorPersistence({ doc, initialDocument, draftId, layoutKey });

  const nodeIds = useMemo(() => doc.graph.nodes.map((node) => node.id), [doc.graph.nodes]);
  const selected = useMemo(
    () => selection.filter((id) => nodeIds.includes(id)),
    [selection, nodeIds],
  );
  const primary = selected.length === 1 ? (selected[0] ?? null) : null;

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
    const center = canvasApi.current?.centerPosition() ?? { x: 0, y: 0 };
    const at = position ?? {
      x: Math.round(center.x + offset - 120),
      y: Math.round(center.y + offset - 40),
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

  const run = runButtonState({
    readOnly,
    runVersionId,
    draftId,
    saveState,
    live: services.mode === 'live',
    saving,
    hasErrors: hasErrorsNow(validated, stale),
    storedVersionValid: initialValidation?.isValid,
  });

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

  const inspectorActions = createInspectorActions({
    execute,
    catalog,
    select: setSelection,
    openConnect: (nodeId, branch) => setConnectTo({ nodeId, branch }),
  });

  useEditorShortcuts({
    openAdd: readOnly ? null : () => setAddOpen(true),
    save: draftId ? () => void saveVersion() : null,
    undo: () => dispatch({ type: 'undo' }),
    redo: () => dispatch({ type: 'redo' }),
    fit: () => canvasApi.current?.fit(),
    layout: runLayout,
    blocked: addOpen || connectTo !== null,
  });

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
        onValidate={() => void validate(doc.graph)}
        run={run}
        onSave={() => void saveVersion()}
        onRun={() => void startRun()}
        onEdit={() => onEdit(doc)}
      />
      <EditorNotices
        readOnly={readOnly}
        editLabel={editLabel}
        saveNotice={notice}
        onDismissSaveNotice={dismissNotice}
        rejection={state.notice}
        onDismissRejection={() => dispatch({ type: 'dismissNotice' })}
      />

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
            diagnostics={visibleDiagnostics(validated, stale)}
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
            availability={availabilityView(validated, stale, primary)}
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
        {state.announcement ? t(state.announcement.key, state.announcement.params) : ''}
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
