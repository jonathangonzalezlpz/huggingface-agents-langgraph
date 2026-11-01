import * as Dialog from '@radix-ui/react-dialog';
import { useId, useState } from 'react';
import type { KeyboardEvent } from 'react';

import { groupComponents } from '../../domain/catalog';
import { END, type EditorNode } from '../../domain/editor/model';
import type { Catalog } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { CATEGORY_STYLE } from '../components/categoryStyle';
import { useComponentDescription } from '../components/componentText';
import { filterComponents } from './componentSearch';

const OVERLAY = 'fixed inset-0 z-40 bg-black/50';
const CONTENT =
  'fixed top-24 left-1/2 z-50 w-[min(34rem,92vw)] -translate-x-1/2 rounded-xl border border-line-strong bg-surface p-5 text-fg shadow-xl';
const BUTTON =
  'min-h-9 rounded-lg border px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60';

/** Ctrl+K: find a component and add it to the graph. */
export function AddComponentDialog({
  open,
  catalog,
  onClose,
  onAdd,
}: {
  open: boolean;
  catalog: Catalog;
  onClose: () => void;
  onAdd: (implementationId: string) => void;
}) {
  const { t } = useI18n();
  const describe = useComponentDescription();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const listId = useId();

  const matches = filterComponents(catalog.components, query, describe);
  const ordered = groupComponents({ ...catalog, components: matches }).flatMap(
    (group) => group.components,
  );
  const current = Math.min(active, Math.max(ordered.length - 1, 0));

  const choose = (implementationId: string) => {
    onAdd(implementationId);
    onClose();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActive(Math.min(current + 1, ordered.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive(Math.max(current - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const picked = ordered[current];
      if (picked) choose(picked.implementationId);
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setQuery('');
          setActive(0);
          onClose();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className={OVERLAY} />
        <Dialog.Content aria-describedby={undefined} className={CONTENT}>
          <Dialog.Title className="mb-3 text-base font-semibold">
            {t('editor.command.title')}
          </Dialog.Title>
          <input
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={ordered[current] ? `${listId}-${current}` : undefined}
            aria-label={t('editor.palette.search')}
            value={query}
            placeholder={t('editor.command.placeholder')}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            className="min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm"
          />
          <ul
            id={listId}
            role="listbox"
            aria-label={t('editor.palette')}
            className="mt-3 max-h-72 space-y-1 overflow-y-auto"
          >
            {ordered.length === 0 && (
              <li className="px-2 py-3 text-sm text-fg-muted">{t('editor.palette.empty')}</li>
            )}
            {ordered.map((component, index) => {
              const { Icon, text } = CATEGORY_STYLE[component.category];
              return (
                <li key={component.implementationId} role="presentation">
                  <button
                    type="button"
                    role="option"
                    id={`${listId}-${index}`}
                    aria-selected={index === current}
                    tabIndex={-1}
                    onClick={() => choose(component.implementationId)}
                    className={`flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left ${
                      index === current ? 'bg-accent-soft' : 'hover:bg-muted'
                    }`}
                  >
                    <Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${text}`} />
                    <span>
                      <span className="block font-mono text-sm font-medium">
                        {component.implementationId}
                      </span>
                      <span className="block text-xs text-fg-muted">{describe(component)}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** "Connect to…": the keyboard-accessible alternative to dragging a connection. */
export function ConnectDialog({
  node,
  nodeIds,
  initialBranch,
  onClose,
  onConfirm,
}: {
  node: EditorNode | null;
  nodeIds: readonly string[];
  initialBranch: string | null;
  onClose: () => void;
  onConfirm: (target: string, branch: string | null) => void;
}) {
  const { t } = useI18n();
  const branchId = useId();
  const targetId = useId();
  const decision = node?.outgoing.kind === 'decision' ? node.outgoing : null;
  const labels = decision ? Object.keys(decision.branches) : [];

  const [branch, setBranch] = useState<string | null>(null);
  const [target, setTarget] = useState<string | null>(null);

  const effectiveBranch = decision ? (branch ?? initialBranch ?? labels[0] ?? null) : null;
  const currentTarget =
    node?.outgoing.kind === 'direct'
      ? node.outgoing.target
      : decision && effectiveBranch
        ? decision.branches[effectiveBranch]
        : null;
  const effectiveTarget = target ?? currentTarget ?? nodeIds[0] ?? END;

  const reset = () => {
    setBranch(null);
    setTarget(null);
  };

  return (
    <Dialog.Root
      open={node !== null}
      onOpenChange={(next) => {
        if (!next) {
          reset();
          onClose();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className={OVERLAY} />
        <Dialog.Content aria-describedby={undefined} className={CONTENT}>
          <Dialog.Title className="mb-4 text-base font-semibold">
            {t('editor.connect.title', { node: node?.id ?? '' })}
          </Dialog.Title>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onConfirm(effectiveTarget, effectiveBranch);
              reset();
            }}
            className="space-y-4"
          >
            {decision && (
              <div>
                <label htmlFor={branchId} className="mb-1 block text-sm font-medium">
                  {t('editor.connect.branch')}
                </label>
                <select
                  id={branchId}
                  value={effectiveBranch ?? ''}
                  onChange={(event) => {
                    setBranch(event.target.value);
                    setTarget(null);
                  }}
                  className="min-h-10 w-full rounded-lg border border-line-strong bg-surface px-2 text-sm"
                >
                  {labels.map((label) => (
                    <option key={label} value={label}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label htmlFor={targetId} className="mb-1 block text-sm font-medium">
                {t('editor.connect.target')}
              </label>
              <select
                id={targetId}
                value={effectiveTarget}
                onChange={(event) => setTarget(event.target.value)}
                className="min-h-10 w-full rounded-lg border border-line-strong bg-surface px-2 text-sm"
              >
                {nodeIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
                <option value={END}>{t('editor.connect.end')}</option>
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <Dialog.Close className={`${BUTTON} border-line-strong bg-surface hover:bg-muted`}>
                {t('editor.cancel')}
              </Dialog.Close>
              <button
                type="submit"
                className={`${BUTTON} border-transparent bg-accent text-on-accent hover:opacity-90`}
              >
                {t('editor.connect.confirm')}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
