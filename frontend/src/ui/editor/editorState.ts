import type { CommandResult, Rejection } from '../../domain/editor/commands';
import {
  canRedo,
  canUndo,
  commit,
  createHistory,
  redo,
  undo,
  type History,
} from '../../domain/editor/history';
import type { EditorDocument } from '../../domain/editor/model';
import type { MessageKey, Params } from '../../i18n';

/** A message for assistive technology, announced after a change. */
export interface Announcement {
  /** Increases on every announcement so an identical message is announced again. */
  serial: number;
  key: MessageKey;
  params: Params;
}

export interface EditorState {
  history: History<EditorDocument>;
  notice: Rejection | null;
  announcement: Announcement | null;
  serial: number;
}

type Announce = (doc: EditorDocument) => { key: MessageKey; params?: Params } | null;

export type EditorAction =
  | { type: 'apply'; run: (doc: EditorDocument) => CommandResult; announce?: Announce }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'dismissNotice' };

export function initialState(document: EditorDocument): EditorState {
  return { history: createHistory(document), notice: null, announcement: null, serial: 0 };
}

function announced(state: EditorState, key: MessageKey, params: Params = {}): EditorState {
  const serial = state.serial + 1;
  return { ...state, serial, announcement: { serial, key, params } };
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case 'apply': {
      const result = action.run(state.history.present);
      if (!result.ok) return { ...state, notice: result.reason };
      const history = commit(state.history, result.doc);
      if (history === state.history) return { ...state, notice: null };
      const next: EditorState = { ...state, history, notice: null };
      const message = action.announce?.(result.doc);
      return message ? announced(next, message.key, message.params) : next;
    }
    case 'undo': {
      const history = undo(state.history);
      return history === state.history
        ? state
        : announced({ ...state, history, notice: null }, 'editor.announce.undone');
    }
    case 'redo': {
      const history = redo(state.history);
      return history === state.history
        ? state
        : announced({ ...state, history, notice: null }, 'editor.announce.redone');
    }
    case 'dismissNotice':
      return state.notice ? { ...state, notice: null } : state;
  }
}

export const canUndoState = (state: EditorState) => canUndo(state.history);
export const canRedoState = (state: EditorState) => canRedo(state.history);

/** Run several commands as one undoable step; the first rejection rejects them all. */
export function sequence(
  ...steps: ((doc: EditorDocument) => CommandResult)[]
): (doc: EditorDocument) => CommandResult {
  return (doc) => {
    let current = doc;
    for (const step of steps) {
      const result = step(current);
      if (!result.ok) return result;
      current = result.doc;
    }
    return { ok: true, doc: current };
  };
}
