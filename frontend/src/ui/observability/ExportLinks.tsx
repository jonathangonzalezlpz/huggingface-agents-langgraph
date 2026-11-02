import { Download } from 'lucide-react';

import type { ExportLink } from '../../domain/trace';
import { useI18n } from '../../i18n/I18nProvider';

/** Download links for the exports of a trace or a battery, labelled by format only. */
export function ExportLinks({ links }: { links: ExportLink[] }) {
  const { t } = useI18n();
  return (
    <div
      className="flex flex-wrap items-center gap-2"
      role="group"
      aria-label={t('obs.export.title')}
    >
      <span className="text-xs font-medium text-fg-muted">{t('obs.export.title')}</span>
      {links.map((link) => (
        <a
          key={link.format}
          href={link.url}
          download={link.filename}
          className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-line-strong px-2.5 text-sm font-medium hover:bg-muted"
        >
          <Download aria-hidden="true" className="size-3.5" />
          {link.format}
        </a>
      ))}
    </div>
  );
}
