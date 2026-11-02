import type { Rejection } from '../../domain/editor/commands';
import { useI18n } from '../../i18n/I18nProvider';
import { NoticeBar } from './NoticeBar';
import { rejectionText } from './rejectionText';
import type { Notice } from './useVersionSaving';

/** Everything the editor says under the toolbar: the read-only hint, save result and refusals. */
export function EditorNotices({
  readOnly,
  editLabel,
  saveNotice,
  onDismissSaveNotice,
  rejection,
  onDismissRejection,
}: {
  readOnly: boolean;
  editLabel: 'editor.edit' | 'editor.duplicate';
  saveNotice: Notice;
  onDismissSaveNotice: () => void;
  rejection: Rejection | null;
  onDismissRejection: () => void;
}) {
  const { t } = useI18n();
  return (
    <>
      {readOnly && (
        <p className="border-b border-line bg-muted px-4 py-1.5 text-xs text-fg-muted">
          {t(editLabel === 'editor.edit' ? 'editor.readOnlyHint.saved' : 'editor.readOnlyHint')}
        </p>
      )}
      {saveNotice && (
        <NoticeBar
          tone={saveNotice.tone}
          role="status"
          text={saveNotice.text}
          onDismiss={onDismissSaveNotice}
        />
      )}
      {rejection && (
        <NoticeBar
          tone="warning"
          role="alert"
          text={rejectionText(t, rejection)}
          onDismiss={onDismissRejection}
        />
      )}
    </>
  );
}
