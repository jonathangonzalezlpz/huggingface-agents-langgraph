import { X } from 'lucide-react';

import { useI18n } from '../../i18n/I18nProvider';

const TONES = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  error: 'bg-error-soft text-error',
} as const;

/** A one-line message under the toolbar that the user can dismiss. */
export function NoticeBar({
  tone,
  role,
  text,
  onDismiss,
}: {
  tone: keyof typeof TONES;
  /** `alert` interrupts a screen reader; `status` waits for a pause. */
  role: 'alert' | 'status';
  text: string;
  onDismiss: () => void;
}) {
  const { t } = useI18n();
  return (
    <div
      role={role}
      className={`flex items-center justify-between gap-3 border-b border-line px-4 py-1.5 text-sm ${TONES[tone]}`}
    >
      <span>{text}</span>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={t('editor.cancel')}
        className="inline-flex size-7 items-center justify-center rounded-md hover:bg-surface/50"
      >
        <X aria-hidden="true" className="size-4" />
      </button>
    </div>
  );
}
