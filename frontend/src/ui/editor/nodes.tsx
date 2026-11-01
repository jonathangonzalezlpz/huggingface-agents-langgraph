import { Handle, Position, type NodeProps } from '@xyflow/react';
import { AlertTriangle, CheckCircle2, Flag, Info, ShieldCheck, XCircle } from 'lucide-react';

import { summarizeParams } from '../../domain/editor/params';
import { useI18n } from '../../i18n/I18nProvider';
import { CATEGORY_STYLE } from '../components/categoryStyle';
import {
  INPUT_HANDLE,
  OUTPUT_HANDLE,
  branchHandle,
  type ComponentFlowNode,
  type TerminalFlowNode,
} from './projection';

const SEVERITY_ICON = { error: XCircle, warning: AlertTriangle, info: Info } as const;
const SEVERITY_TONE = {
  error: 'text-error',
  warning: 'text-warning',
  info: 'text-info',
} as const;

const RUN_CLASSES = {
  none: '',
  visited: '',
  skipped: 'opacity-40',
  active: 'ring-2 ring-accent',
  failed: 'border-error ring-2 ring-error',
} as const;

export function ComponentNode({ data, selected }: NodeProps<ComponentFlowNode>) {
  const { t, tp } = useI18n();
  const { node, component, isEntry, severity, diagnosticCount, run } = data;
  const style = CATEGORY_STYLE[component?.category ?? 'other'];
  const SeverityIcon = severity ? SEVERITY_ICON[severity] : CheckCircle2;
  const { outgoing } = node;

  return (
    <div
      data-run={run?.state}
      className={`h-full w-full overflow-hidden rounded-xl border border-l-4 bg-surface text-fg shadow-sm ${style.border} ${
        selected ? 'border-accent ring-2 ring-accent' : 'border-line-strong'
      } ${RUN_CLASSES[run?.state ?? 'none']}`}
    >
      <Handle type="target" position={Position.Left} id={INPUT_HANDLE} />
      <div className="flex items-start gap-2 px-3 pt-2.5">
        <style.Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${style.text}`} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-sm font-semibold">{node.id}</p>
          {node.id !== node.implementationId && (
            <p className="truncate font-mono text-xs text-fg-muted">{node.implementationId}</p>
          )}
          {summarizeParams(node.params, component?.params ?? []).length > 0 && (
            <p className="truncate font-mono text-xs text-fg-muted">
              {summarizeParams(node.params, component?.params ?? []).join(' · ')}
            </p>
          )}
          {run && run.visits > 0 && (
            <p className="truncate text-xs text-fg-muted">
              {tp('runs.visits', run.visits)} · {run.seconds.toFixed(1)} s
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {isEntry && (
            <span title={t('editor.node.entry')} className="text-accent-fg">
              <Flag aria-hidden="true" className="size-3.5" />
              <span className="sr-only">{t('editor.node.entry')}</span>
            </span>
          )}
          {component?.recoverErrors && (
            <span title={t('builder.recoversErrors')} className="text-fg-muted">
              <ShieldCheck aria-hidden="true" className="size-3.5" />
              <span className="sr-only">{t('builder.recoversErrors')}</span>
            </span>
          )}
          {run?.state === 'failed' && (
            <span className="text-error" title={t('runs.status.error')}>
              <XCircle aria-hidden="true" className="size-3.5" />
              <span className="sr-only">{t('runs.status.error')}</span>
            </span>
          )}
          {severity && (
            <span className={`inline-flex items-center gap-0.5 text-xs ${SEVERITY_TONE[severity]}`}>
              <SeverityIcon aria-hidden="true" className="size-3.5" />
              {diagnosticCount}
            </span>
          )}
        </div>
      </div>

      {outgoing.kind === 'decision' ? (
        <ul className="mt-2 border-t border-line">
          {Object.entries(outgoing.branches).map(([label, target]) => (
            <li
              key={label}
              className="relative flex h-[26px] items-center justify-end pr-4 pl-3 text-xs"
            >
              <span className="mr-auto text-fg-muted">{label}</span>
              <span className={target === null ? 'text-warning' : 'font-mono text-fg'}>
                {target === null ? t('editor.node.pending') : target}
              </span>
              <Handle type="source" position={Position.Right} id={branchHandle(label)} />
            </li>
          ))}
        </ul>
      ) : (
        <Handle type="source" position={Position.Right} id={OUTPUT_HANDLE} />
      )}
    </div>
  );
}

export function TerminalNode({ data }: NodeProps<TerminalFlowNode>) {
  const { t } = useI18n();
  const isEnd = data.kind === 'end';
  return (
    <div className="flex h-10 w-[72px] items-center justify-center rounded-full border border-line-strong bg-muted text-xs font-semibold text-fg-muted">
      {isEnd ? t('editor.node.end') : t('editor.node.start')}
      {isEnd ? (
        <Handle type="target" position={Position.Left} id={INPUT_HANDLE} />
      ) : (
        <Handle type="source" position={Position.Right} id={OUTPUT_HANDLE} isConnectable={false} />
      )}
    </div>
  );
}

export const nodeTypes = { component: ComponentNode, terminal: TerminalNode };
