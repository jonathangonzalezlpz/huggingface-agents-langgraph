import { useEffect, useRef } from 'react';

export interface ShortcutHandlers {
  /** Ctrl+K works even while typing; the rest do not. */
  openAdd: (() => void) | null;
  save: (() => void) | null;
  undo: () => void;
  redo: () => void;
  fit: () => void;
  layout: () => void;
  /** A dialog is open: only Ctrl+K is still listened to. */
  blocked: boolean;
}

function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return !!element && (element.matches('input, textarea, select') || element.isContentEditable);
}

/**
 * Editor keyboard shortcuts: Ctrl+K add, Ctrl+S save, Ctrl+Z / Ctrl+Y undo and redo, F fit and
 * L layout. The newest handlers are kept in a ref, so the listener is attached only once.
 */
export function useEditorShortcuts(handlers: ShortcutHandlers) {
  const current = useRef(handlers);
  useEffect(() => {
    current.current = handlers;
  });

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      const h = current.current;
      const mod = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();
      if (mod && key === 'k') {
        event.preventDefault();
        h.openAdd?.();
        return;
      }
      if (isTyping(event.target) || h.blocked) return;
      if (mod && key === 's' && h.save) {
        event.preventDefault();
        h.save();
      } else if (mod && key === 'z') {
        event.preventDefault();
        if (event.shiftKey) h.redo();
        else h.undo();
      } else if (mod && key === 'y') {
        event.preventDefault();
        h.redo();
      } else if (!mod && key === 'f') {
        h.fit();
      } else if (!mod && key === 'l') {
        h.layout();
      }
    };
    document.addEventListener('keydown', listener);
    return () => document.removeEventListener('keydown', listener);
  }, []);
}
