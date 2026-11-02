import { Link, useNavigate } from 'react-router-dom';

import { shortHash } from '../../domain/catalog';
import { diffDefinitions } from '../../domain/diff';
import type { Architecture } from '../../domain/types';
import type { ArchitectureGroup } from '../../domain/versions';
import { useI18n } from '../../i18n/I18nProvider';
import { describeDiff } from '../components/diffText';
import { StatusBadge } from '../components/StatusBadge';
import { startEditing } from '../editor/drafts';
import { useServices } from '../services';

const BUTTON =
  'inline-flex min-h-9 items-center rounded-lg border border-line-strong bg-surface px-3 text-sm font-medium hover:bg-muted';

const openPath = (architecture: Architecture) =>
  `/builder/architecture/${encodeURIComponent(architecture.id)}`;

function versionLabel(architecture: Architecture, builtin: string, version: string): string {
  return architecture.version === null ? builtin : version;
}

/** One architecture with its latest version, and its history when it has more than one. */
export function ArchitectureGroupCard({ group }: { group: ArchitectureGroup<Architecture> }) {
  const { t, tp, language } = useI18n();
  const services = useServices();
  const navigate = useNavigate();
  const { latest } = group;
  const { validation } = latest;
  const date = (value: string | null) =>
    value
      ? new Date(value).toLocaleDateString(language, {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
        })
      : '';

  const edit = () => {
    void startEditing(services, latest).then((id) => navigate(`/builder/draft/${id}`));
  };

  return (
    <li className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-mono text-base font-semibold">{group.architectureId}</h3>
          <p className="mt-1 text-sm text-fg-muted">
            {latest.version === null
              ? t('builder.builtin')
              : t('builder.latest', { version: latest.version })}
            {' · '}
            <span className="font-mono">{shortHash(latest.contentSha256)}</span>
            {' · '}
            {tp('builder.components', latest.definition.nodes.length)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {latest.readOnly && <StatusBadge tone="neutral">{t('builder.readOnly')}</StatusBadge>}
          <StatusBadge tone={validation.isValid ? 'success' : 'error'}>
            {validation.isValid ? t('builder.validation.valid') : t('builder.validation.invalid')}
          </StatusBadge>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted">
          {tp('diagnostics.errors', validation.counts.error)}
          {' · '}
          {tp('diagnostics.warnings', validation.counts.warning)}
          {' · '}
          {tp('diagnostics.infos', validation.counts.info)}
        </p>
        <div className="flex gap-2">
          <Link
            to={openPath(latest)}
            aria-label={`${t('builder.open')} ${group.architectureId}`}
            className={BUTTON}
          >
            {t('builder.open')}
          </Link>
          <button
            type="button"
            onClick={edit}
            aria-label={`${t(latest.readOnly ? 'editor.duplicate' : 'builder.edit')} ${group.architectureId}`}
            className={BUTTON}
          >
            {t(latest.readOnly ? 'editor.duplicate' : 'builder.edit')}
          </button>
        </div>
      </div>

      {group.versions.length > 1 && (
        <details className="mt-4 border-t border-line pt-3">
          <summary className="cursor-pointer text-sm font-medium">
            {t('builder.history')} · {tp('builder.history.versions', group.versions.length)}
          </summary>
          <ol className="mt-3 space-y-2">
            {group.versions.map((entry) => (
              <li
                key={entry.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted px-3 py-2 text-sm"
              >
                <span>
                  <span className="font-semibold">
                    {versionLabel(entry, t('builder.builtin'), `v${entry.version}`)}
                  </span>
                  {' · '}
                  <span className="text-fg-muted">{date(entry.createdAt)}</span>
                  {' · '}
                  <span className="font-mono text-fg-muted">{shortHash(entry.contentSha256)}</span>
                  <span className="block text-fg-muted">
                    {entry.previous
                      ? describeDiff(
                          t,
                          tp,
                          diffDefinitions(entry.previous.definition, entry.definition),
                        )
                      : t('builder.history.initial')}
                  </span>
                </span>
                <Link
                  to={openPath(entry)}
                  aria-label={`${t('builder.open')} ${group.architectureId} v${entry.version}`}
                  className={BUTTON}
                >
                  {t('builder.open')}
                </Link>
              </li>
            ))}
          </ol>
        </details>
      )}
    </li>
  );
}
