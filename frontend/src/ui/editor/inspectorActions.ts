import {
  clearDecision,
  disconnect,
  disconnectBranch,
  removeNode,
  renameArchitecture,
  renameNode,
  setDecision,
  setDescription,
  setInitial,
  setParam,
} from '../../domain/editor/commands';
import type { Catalog } from '../../domain/types';
import type { EditorAction } from './editorState';
import type { InspectorActions } from './Inspector';

type Execute = (
  run: Extract<EditorAction, { type: 'apply' }>['run'],
  announce?: Extract<EditorAction, { type: 'apply' }>['announce'],
  onSuccess?: () => void,
) => void;

/** What the inspector can do to the selected node, each as one editor command plus its message. */
export function createInspectorActions({
  execute,
  catalog,
  select,
  openConnect,
}: {
  execute: Execute;
  catalog: Catalog;
  select: (ids: string[]) => void;
  openConnect: (nodeId: string, branch: string | null) => void;
}): InspectorActions {
  return {
    rename: (id, newId) =>
      execute(
        (doc) => renameNode(doc, id, newId),
        () => ({ key: 'editor.announce.renamed', params: { id, newId } }),
        () => select([newId]),
      ),
    setEntry: (id) =>
      execute(
        (doc) => setInitial(doc, id),
        () => ({ key: 'editor.announce.entry', params: { id } }),
      ),
    remove: (id) =>
      execute(
        (doc) => removeNode(doc, id),
        () => ({ key: 'editor.announce.removed', params: { id } }),
        () => select([]),
      ),
    openConnect,
    disconnect: (nodeId, branch) =>
      execute(
        (doc) => (branch ? disconnectBranch(doc, nodeId, branch) : disconnect(doc, nodeId)),
        () => ({ key: 'editor.announce.disconnected', params: { source: nodeId } }),
      ),
    setDecision: (nodeId, strategy) =>
      execute(
        (doc) =>
          strategy === ''
            ? clearDecision(doc, nodeId)
            : setDecision(doc, catalog, nodeId, strategy),
        () => ({ key: 'editor.announce.decision', params: { id: nodeId, strategy } }),
      ),
    setDescription: (nodeId, text) => execute((doc) => setDescription(doc, nodeId, text)),
    setParam: (nodeId, name, value) =>
      execute(
        (doc) => setParam(doc, catalog, nodeId, name, value),
        () => ({
          key: value === null ? 'editor.announce.paramReset' : 'editor.announce.param',
          params: { id: nodeId, name },
        }),
      ),
    renameArchitecture: (name) => execute((doc) => renameArchitecture(doc, name)),
  };
}
