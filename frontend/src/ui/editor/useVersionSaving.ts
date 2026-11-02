import { useMemo, useState } from 'react';

import { toDefinition, unexportableDecisions } from '../../domain/editor/convert';
import type { EditorDocument } from '../../domain/editor/model';
import { StudioError } from '../../domain/errors';
import { useI18n } from '../../i18n/I18nProvider';
import type { SavedMarker } from '../../ports';
import { useServices } from '../services';

export type Notice = { tone: 'success' | 'warning' | 'error'; text: string } | null;
export type SaveState = 'saved' | 'unsaved' | null;

/**
 * Saving a local draft as a stored version. A draft remembers which version it was saved as,
 * so the toolbar can say whether it is up to date; a version with errors is saved but not
 * offered to run.
 */
export function useVersionSaving({ doc, draftId }: { doc: EditorDocument; draftId?: string }) {
  const { t, tp } = useI18n();
  const services = useServices();
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [marker, setMarker] = useState<SavedMarker | null>(() =>
    draftId ? services.drafts.savedMarker(draftId) : null,
  );
  const currentJson = useMemo(() => JSON.stringify(toDefinition(doc.graph)), [doc.graph]);

  const saveState: SaveState = draftId
    ? marker && marker.definitionJson === currentJson
      ? 'saved'
      : 'unsaved'
    : null;

  /** Resolves to the version id only when it is clean enough to run. */
  const saveVersion = async (): Promise<string | null> => {
    if (!draftId) return null;
    if (doc.graph.nodes.length === 0) {
      setNotice({ tone: 'error', text: t('editor.save.empty') });
      return null;
    }
    const snapshot = doc;
    setSaving(true);
    setNotice(null);
    try {
      const { architecture, created } = await services.architectures.save(
        toDefinition(snapshot.graph),
      );
      const saved: SavedMarker = {
        versionId: architecture.id,
        version: architecture.version ?? 0,
        definitionJson: currentJson,
      };
      services.drafts.save(draftId, snapshot);
      services.drafts.markSaved(draftId, saved);
      setMarker(saved);

      const errors = architecture.validation.counts.error;
      const dropped = unexportableDecisions(snapshot.graph);
      const parts = [
        created
          ? t('editor.save.created', { version: saved.version })
          : t('editor.save.existing', { version: saved.version }),
      ];
      if (errors > 0) parts.push(tp('editor.save.withErrors', errors));
      if (dropped.length > 0) parts.push(t('editor.save.dropped', { ids: dropped.join(', ') }));
      setNotice({
        tone: errors > 0 || dropped.length > 0 ? 'warning' : 'success',
        text: parts.join(' '),
      });
      return errors === 0 && dropped.length === 0 ? architecture.id : null;
    } catch (error) {
      const unavailable = error instanceof StudioError && error.kind === 'unavailable';
      setNotice({
        tone: 'error',
        text: t(unavailable ? 'editor.save.unavailable' : 'editor.save.failed'),
      });
      return null;
    } finally {
      setSaving(false);
    }
  };

  return {
    marker,
    saving,
    notice,
    dismissNotice: () => setNotice(null),
    saveState,
    saveVersion,
  };
}
