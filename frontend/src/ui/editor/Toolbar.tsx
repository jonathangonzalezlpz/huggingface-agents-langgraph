import {
  ArrowLeft,
  Copy,
  LayoutGrid,
  Maximize,
  Plus,
  Redo2,
  ShieldCheck,
  Undo2,
} from 'lucide-react';
import type { ComponentType, ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n';
import { StatusBadge } from '../components/StatusBadge';

const BUTTON =
  'inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-2.5 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50';

function ToolButton({
  label,
  Icon,
  onClick,
  disabled,
  hideLabel,
  children,
}: {
  label: MessageKey;
  Icon: ComponentType<{ className?: string }>;
  onClick: () => void;
  disabled?: boolean;
  hideLabel?: boolean;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled ?? false}
      title={t(label)}
      aria-label={hideLabel ? t(label) : undefined}
      className={BUTTON}
    >
      <Icon aria-hidden="true" className="size-4" />
      {!hideLabel && <span className="hidden xl:inline">{t(label)}</span>}
      {children}
    </button>
  );
}

export function Toolbar({
  title,
  draft,
  readOnly,
  canUndo,
  canRedo,
  validating,
  onUndo,
  onRedo,
  onAdd,
  onLayout,
  onFit,
  onValidate,
  onDuplicate,
}: {
  title: string;
  draft: boolean;
  readOnly: boolean;
  canUndo: boolean;
  canRedo: boolean;
  validating: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onAdd: () => void;
  onLayout: () => void;
  onFit: () => void;
  onValidate: () => void;
  onDuplicate: () => void;
}) {
  const { t } = useI18n();
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line bg-surface px-3 py-2">
      <Link
        to="/builder"
        aria-label={t('editor.back')}
        title={t('editor.back')}
        className="inline-flex size-9 items-center justify-center rounded-lg text-fg-muted hover:bg-muted hover:text-fg"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
      </Link>
      <h1 className="font-mono text-sm font-semibold">{title}</h1>
      {draft && <StatusBadge tone="info">{t('editor.badge.draft')}</StatusBadge>}
      {readOnly && <StatusBadge tone="neutral">{t('editor.badge.readOnly')}</StatusBadge>}

      <div
        role="toolbar"
        aria-label={t('editor.toolbar')}
        className="ml-auto flex flex-wrap gap-1.5"
      >
        <ToolButton
          label="editor.undo"
          Icon={Undo2}
          onClick={onUndo}
          disabled={!canUndo}
          hideLabel
        />
        <ToolButton
          label="editor.redo"
          Icon={Redo2}
          onClick={onRedo}
          disabled={!canRedo}
          hideLabel
        />
        <ToolButton label="editor.add" Icon={Plus} onClick={onAdd} disabled={readOnly} />
        <ToolButton label="editor.layout" Icon={LayoutGrid} onClick={onLayout} />
        <ToolButton label="editor.fit" Icon={Maximize} onClick={onFit} />
        <ToolButton
          label="editor.validate"
          Icon={ShieldCheck}
          onClick={onValidate}
          disabled={validating}
        />
        {readOnly && <ToolButton label="editor.duplicate" Icon={Copy} onClick={onDuplicate} />}
      </div>
    </header>
  );
}
