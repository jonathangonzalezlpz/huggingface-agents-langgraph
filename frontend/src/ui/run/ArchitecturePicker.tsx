import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import type { Architecture } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { ErrorNotice } from '../components/ErrorNotice';
import type { Library } from '../hooks/useLibrary';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';

function useVersionLabel() {
  const { t } = useI18n();
  return (architecture: Architecture): string => {
    const name = architecture.architectureId;
    const version = architecture.version;
    if (version === null) return t('runs.architecture.builtin', { name });
    return architecture.validation.isValid
      ? t('runs.architecture.version', { name, version })
      : t('runs.architecture.invalid', { name, version });
  };
}

/**
 * Choose a stored version. With `runnableOnly` the versions that have validation errors are not
 * offered; otherwise they are listed, and choosing one explains why it cannot run.
 */
export function ArchitecturePicker({
  id,
  library,
  value,
  onChange,
  disabled = false,
  runnableOnly = false,
}: {
  id: string;
  library: Library;
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
  runnableOnly?: boolean;
}) {
  const { t } = useI18n();
  const label = useVersionLabel();
  const options = useMemo(() => {
    if (library.status !== 'success') return [];
    const usable = runnableOnly ? library.data.filter((a) => a.validation.isValid) : library.data;
    return [...usable].sort((a, b) => a.architectureId.localeCompare(b.architectureId));
  }, [library, runnableOnly]);
  const selected = options.find((item) => item.id === value) ?? null;
  const blocked = selected !== null && !selected.validation.isValid;

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {t('runs.architecture')}
      </label>
      {library.status === 'error' ? (
        <ErrorNotice error={library.error} onRetry={library.reload} />
      ) : (
        <select
          id={id}
          className={FIELD}
          value={value ?? ''}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">{t('runs.architecture.placeholder')}</option>
          {options.map((item) => (
            <option key={item.id} value={item.id}>
              {label(item)}
            </option>
          ))}
        </select>
      )}
      {library.status === 'success' && options.length === 0 && (
        <p className="mt-1 text-sm text-fg-muted">{t('runs.architecture.none')}</p>
      )}
      {blocked && selected && (
        <p role="alert" className="mt-2 text-sm text-error">
          {t('runs.architecture.blocked')}{' '}
          <Link
            to={`/builder/architecture/${encodeURIComponent(selected.id)}`}
            className="underline underline-offset-2"
          >
            {t('runs.architecture.open')}
          </Link>
        </p>
      )}
    </div>
  );
}
