import {
  BrainCircuit,
  Download,
  Flag,
  ListChecks,
  LogIn,
  Search,
  Shapes,
  ShieldCheck,
  Wrench,
} from 'lucide-react';
import type { ComponentType } from 'react';

import type { Category } from '../../domain/types';

interface CategoryStyle {
  Icon: ComponentType<{ className?: string }>;
  /** Tailwind classes are spelled out in full so they are generated. */
  text: string;
  border: string;
  cssColor: string;
}

/** Icon and colour per category. The icon, not the colour, is what tells them apart. */
export const CATEGORY_STYLE: Record<Category, CategoryStyle> = {
  input: {
    Icon: LogIn,
    text: 'text-cat-input',
    border: 'border-l-cat-input',
    cssColor: 'var(--cat-input)',
  },
  acquisition: {
    Icon: Download,
    text: 'text-cat-acquisition',
    border: 'border-l-cat-acquisition',
    cssColor: 'var(--cat-acquisition)',
  },
  research: {
    Icon: Search,
    text: 'text-cat-research',
    border: 'border-l-cat-research',
    cssColor: 'var(--cat-research)',
  },
  planning: {
    Icon: ListChecks,
    text: 'text-cat-planning',
    border: 'border-l-cat-planning',
    cssColor: 'var(--cat-planning)',
  },
  verification: {
    Icon: ShieldCheck,
    text: 'text-cat-verification',
    border: 'border-l-cat-verification',
    cssColor: 'var(--cat-verification)',
  },
  tools: {
    Icon: Wrench,
    text: 'text-cat-tools',
    border: 'border-l-cat-tools',
    cssColor: 'var(--cat-tools)',
  },
  reasoning: {
    Icon: BrainCircuit,
    text: 'text-cat-reasoning',
    border: 'border-l-cat-reasoning',
    cssColor: 'var(--cat-reasoning)',
  },
  output: {
    Icon: Flag,
    text: 'text-cat-output',
    border: 'border-l-cat-output',
    cssColor: 'var(--cat-output)',
  },
  other: {
    Icon: Shapes,
    text: 'text-cat-other',
    border: 'border-l-cat-other',
    cssColor: 'var(--cat-other)',
  },
};
