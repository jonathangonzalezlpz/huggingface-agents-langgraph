import type { DefinitionDiff } from '../../domain/diff';
import type { MessageKey, Params, PluralKey } from '../../i18n';

type Translate = (key: MessageKey, params?: Params) => string;
type TranslatePlural = (base: PluralKey, count: number, params?: Params) => string;

/** One line summarizing what a version changed, in the current language. */
export function describeDiff(t: Translate, tp: TranslatePlural, diff: DefinitionDiff): string {
  const parts = [
    diff.nodesAdded.length > 0 && tp('diff.nodesAdded', diff.nodesAdded.length),
    diff.nodesRemoved.length > 0 && tp('diff.nodesRemoved', diff.nodesRemoved.length),
    diff.nodesChanged.length > 0 && tp('diff.nodesChanged', diff.nodesChanged.length),
    diff.edgesAdded.length > 0 && tp('diff.edgesAdded', diff.edgesAdded.length),
    diff.edgesRemoved.length > 0 && tp('diff.edgesRemoved', diff.edgesRemoved.length),
    diff.entryChanged && t('diff.entry'),
  ].filter((part): part is string => typeof part === 'string');
  return parts.length > 0 ? parts.join(', ') : t('builder.history.nochange');
}
