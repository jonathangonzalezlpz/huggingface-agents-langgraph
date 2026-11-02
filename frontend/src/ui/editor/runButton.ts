import type { SaveState } from './useVersionSaving';

export interface RunButton {
  label: 'editor.run' | 'editor.runSave';
  disabled: boolean;
}

/**
 * What the toolbar's run button says and whether it can be pressed, or null when this view
 * cannot start a run at all. A stored version runs as it is; a draft is saved first unless it
 * already matches its saved version, and nothing runs in demo mode or with validation errors.
 */
export function runButtonState({
  readOnly,
  runVersionId,
  draftId,
  saveState,
  live,
  saving,
  hasErrors,
  storedVersionValid,
}: {
  readOnly: boolean;
  runVersionId?: string | undefined;
  draftId?: string | undefined;
  saveState: SaveState;
  live: boolean;
  saving: boolean;
  hasErrors: boolean;
  storedVersionValid?: boolean | undefined;
}): RunButton | null {
  if (readOnly) {
    return runVersionId
      ? { label: 'editor.run', disabled: !live || storedVersionValid === false }
      : null;
  }
  if (!draftId) return null;
  return {
    label: saveState === 'saved' ? 'editor.run' : 'editor.runSave',
    disabled: !live || saving || hasErrors,
  };
}
