import { CATEGORY_ORDER } from './categories';
import type { Catalog, Category, ComponentInfo } from './types';

export interface ComponentGroup {
  category: Category;
  components: ComponentInfo[];
}

/** Components grouped by category in display order; empty categories are omitted. */
export function groupComponents(catalog: Catalog): ComponentGroup[] {
  return CATEGORY_ORDER.map((category) => ({
    category,
    components: catalog.components
      .filter((component) => component.category === category)
      .sort((a, b) => a.implementationId.localeCompare(b.implementationId)),
  })).filter((group) => group.components.length > 0);
}

/** First characters of a content hash, for display. */
export function shortHash(hash: string): string {
  return hash.slice(0, 7);
}
