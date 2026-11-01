import type { Rejection } from '../../domain/editor/commands';
import type { MessageKey, Params } from '../../i18n';

const KEYS: Record<Rejection['code'], MessageKey> = {
  'invalid-id': 'editor.reject.invalid-id',
  'duplicate-id': 'editor.reject.duplicate-id',
  'unknown-node': 'editor.reject.unknown-node',
  'unknown-component': 'editor.reject.unknown-component',
  'unknown-strategy': 'editor.reject.unknown-strategy',
  'unknown-branch': 'editor.reject.unknown-branch',
  'has-decision': 'editor.reject.has-decision',
  'no-decision': 'editor.reject.no-decision',
  'invalid-position': 'editor.reject.invalid-position',
};

/** The user-facing reason a command was refused, in the current language. */
export function rejectionText(
  t: (key: MessageKey, params?: Params) => string,
  rejection: Rejection,
): string {
  return t(KEYS[rejection.code]);
}
