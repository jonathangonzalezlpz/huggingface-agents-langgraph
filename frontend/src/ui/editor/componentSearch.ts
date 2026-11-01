import type { ComponentInfo } from '../../domain/types';

function fold(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/**
 * Components matching every word of the query in their id or description, ignoring case and
 * accents. An empty query keeps everything.
 */
export function filterComponents(
  components: readonly ComponentInfo[],
  query: string,
  describe: (component: ComponentInfo) => string,
): ComponentInfo[] {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [...components];
  return components.filter((component) => {
    const haystack = fold(`${component.implementationId} ${describe(component)}`);
    return words.every((word) => haystack.includes(word));
  });
}
