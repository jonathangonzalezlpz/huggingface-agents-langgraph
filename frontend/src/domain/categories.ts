import type { Category } from './types';

/** Display order of component categories. */
export const CATEGORY_ORDER: readonly Category[] = [
  'input',
  'acquisition',
  'research',
  'reasoning',
  'output',
  'other',
];

export function isCategory(value: string): value is Category {
  return (CATEGORY_ORDER as readonly string[]).includes(value);
}
