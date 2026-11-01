import { describe, expect, it } from 'vitest';

import { createMemoryServices } from '../adapters/memory/memoryServices';
import { groupComponents, shortHash } from '../domain/catalog';
import { StudioError } from '../domain/errors';
import type { ArchitecturePort } from '../ports';
import { loadLibrary } from './loadLibrary';

describe('groupComponents', () => {
  it('groups by category in display order with sorted members', async () => {
    const catalog = await createMemoryServices().catalog.getCatalog();
    const groups = groupComponents(catalog);
    expect(groups.map((g) => g.category)).toEqual([
      'input',
      'acquisition',
      'research',
      'reasoning',
      'output',
    ]);
    const acquisition = groups.find((g) => g.category === 'acquisition');
    const ids = acquisition?.components.map((c) => c.implementationId) ?? [];
    expect(ids).toEqual([...ids].sort());
    expect(ids).toHaveLength(5);
    expect(groups.reduce((total, g) => total + g.components.length, 0)).toBe(12);
  });

  it('omits categories without components', () => {
    const empty = {
      categories: [],
      components: [],
      routingStrategies: [],
      state: { types: [], fields: [], initialFields: [] },
    };
    expect(groupComponents(empty)).toEqual([]);
  });
});

describe('shortHash', () => {
  it('keeps the first seven characters', () => {
    expect(shortHash('0123456789abcdef')).toBe('0123456');
  });
});

describe('loadLibrary', () => {
  it('returns each listed architecture with definition and validation', async () => {
    const library = await loadLibrary(createMemoryServices().architectures);
    expect(library).toHaveLength(1);
    expect(library[0]?.definition.nodes).toHaveLength(12);
    expect(library[0]?.validation.isValid).toBe(true);
  });

  it('propagates a failure fetching any architecture', async () => {
    const failing: ArchitecturePort = {
      list: () => createMemoryServices().architectures.list(),
      get: () => Promise.reject(new StudioError('network', 'down')),
    };
    await expect(loadLibrary(failing)).rejects.toMatchObject({ kind: 'network' });
  });
});
