import { useEffect, useRef } from 'react';

import type { EditorDocument } from '../../domain/editor/model';
import { useServices } from '../services';

const DRAFT_SAVE_DELAY_MS = 400;
const LAYOUT_SAVE_DELAY_MS = 600;

/**
 * Keep the work safe as it changes. A draft keeps the whole document; a saved or built-in version
 * keeps only where its nodes sit. Nothing is written until something differs from what was loaded,
 * and a draft is written once more when the editor closes so no recent edit is lost.
 */
export function useEditorPersistence({
  doc,
  initialDocument,
  draftId,
  layoutKey,
}: {
  doc: EditorDocument;
  initialDocument: EditorDocument;
  draftId?: string | undefined;
  layoutKey?: string | undefined;
}) {
  const services = useServices();
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
}
