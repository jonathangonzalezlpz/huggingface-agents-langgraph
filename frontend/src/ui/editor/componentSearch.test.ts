import { describe, expect, it } from 'vitest';

import type { ComponentInfo } from '../../domain/types';
import { filterComponents } from './componentSearch';

const contract = {
  requiredInputs: [],
  optionalInputs: [],
  guaranteedOutputs: [],
  optionalOutputs: [],
};
const make = (implementationId: string, description: string): ComponentInfo => ({
  implementationId,
  description,
  category: 'other',
  recoverErrors: false,
  params: [],
  contract,
});

const components = [
  make('web_research', 'Busca en la web y en enciclopedias.'),
  make('document_processing', 'Extrae el texto de documentos PDF.'),
  make('reasoning', 'Razona a partir de la evidencia.'),
];
const describe_ = (component: ComponentInfo) => component.description;

describe('filterComponents', () => {
  it('keeps everything for an empty or blank query', () => {
    expect(filterComponents(components, '', describe_)).toHaveLength(3);
    expect(filterComponents(components, '   ', describe_)).toHaveLength(3);
  });

  it('matches ids and descriptions, ignoring case and accents', () => {
    expect(filterComponents(components, 'WEB', describe_).map((c) => c.implementationId)).toEqual([
      'web_research',
    ]);
    expect(filterComponents(components, 'razona', describe_)).toHaveLength(1);
    expect(filterComponents(components, 'enciclopedia', describe_)).toHaveLength(1);
    expect(filterComponents(components, 'busca', describe_)).toHaveLength(1);
  });

  it('requires every word to match', () => {
    expect(filterComponents(components, 'document pdf', describe_)).toHaveLength(1);
    expect(filterComponents(components, 'document web', describe_)).toHaveLength(0);
  });

  it('returns nothing when nothing matches', () => {
    expect(filterComponents(components, 'zzz', describe_)).toEqual([]);
  });
});
