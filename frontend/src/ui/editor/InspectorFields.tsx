import { useId, useState } from 'react';
import type { FormEvent } from 'react';

import type { CommandResult } from '../../domain/editor/commands';
import type { NodeAvailability } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { rejectionText } from './rejectionText';

const FIELD = 'w-full rounded-lg border border-line-strong bg-surface px-2 text-sm';

/**
 * A text value committed on Enter or when focus leaves. The domain command is tried first, so
 * a refusal is explained next to the field and nothing changes.
 */
export function TextCommitField({
  label,
  value,
  disabled,
  mono,
  multiline,
  validate,
  onCommit,
}: {
  label: string;
  value: string;
  disabled: boolean;
  mono?: boolean;
  multiline?: boolean;
  validate: (next: string) => CommandResult;
  onCommit: (next: string) => void;
}) {
  const { t } = useI18n();
  const fieldId = useId();
  const [draft, setDraft] = useState(value);
  const [problem, setProblem] = useState<CommandResult | null>(null);

  const commit = (event?: FormEvent) => {
    event?.preventDefault();
    if (draft === value) return setProblem(null);
    const attempt = validate(draft);
    if (attempt.ok) {
      setProblem(null);
      onCommit(draft);
    } else {
      setProblem(attempt);
    }
  };

  const shared = {
    id: fieldId,
    value: draft,
    disabled,
    'aria-invalid': problem !== null && !problem.ok,
    'aria-describedby': problem ? `${fieldId}-error` : undefined,
    onBlur: () => commit(),
    className: `${FIELD} ${mono ? 'font-mono' : ''}`,
  };

  return (
    <form onSubmit={commit}>
      <label htmlFor={fieldId} className="mb-1 block text-xs font-medium text-fg-muted">
        {label}
      </label>
      {multiline ? (
        <textarea
          {...shared}
          rows={3}
          onChange={(event) => setDraft(event.target.value)}
          className={`${shared.className} py-1.5`}
        />
      ) : (
        <input
          {...shared}
          onChange={(event) => setDraft(event.target.value)}
          className={`${shared.className} min-h-9`}
        />
      )}
      {problem && !problem.ok && (
        <p id={`${fieldId}-error`} className="mt-1 text-xs text-error">
          {rejectionText(t, problem.reason)}
        </p>
      )}
    </form>
  );
}

/** What the validation says about a node's data, or why nothing can be said yet. */
export type AvailabilityView =
  | { status: 'ready'; node: NodeAvailability | null }
  | { status: 'pending' | 'stale' | 'unavailable' };

function FieldList({ items }: { items: string[] }) {
  const { t } = useI18n();
  return items.length === 0 ? (
    <span className="text-xs text-fg-muted">{t('editor.contract.none')}</span>
  ) : (
    <span className="flex flex-wrap gap-1">
      {items.map((item) => (
        <code key={item} className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
          {item}
        </code>
      ))}
    </span>
  );
}

/** "Data here": the state fields present when the node starts. */
export function AvailabilitySection({ view }: { view: AvailabilityView }) {
  const { t } = useI18n();
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="space-y-2 border-t border-line pt-4">
      <h3 id={heading} className="text-sm font-semibold">
        {t('editor.available')}
      </h3>
      <p className="text-xs text-fg-muted">{t('editor.available.hint')}</p>
      {view.status === 'pending' && (
        <p className="text-xs text-fg-muted">{t('editor.available.pending')}</p>
      )}
      {view.status === 'stale' && (
        <p className="text-xs text-warning">{t('editor.available.stale')}</p>
      )}
      {view.status === 'unavailable' && (
        <p className="text-xs text-warning">{t('editor.available.unavailable')}</p>
      )}
      {view.status === 'ready' && view.node === null && (
        <p className="text-xs text-warning">{t('editor.available.unreachable')}</p>
      )}
      {view.status === 'ready' && view.node !== null && (
        <dl className="space-y-2">
          <div>
            <dt className="mb-0.5 text-xs font-medium text-fg-muted">
              {t('editor.available.guaranteed')}
            </dt>
            <dd>
              <FieldList items={view.node.guaranteed} />
            </dd>
          </div>
          <div>
            <dt className="mb-0.5 text-xs font-medium text-fg-muted">
              {t('editor.available.possible')}
            </dt>
            <dd>
              <FieldList items={view.node.possible} />
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
