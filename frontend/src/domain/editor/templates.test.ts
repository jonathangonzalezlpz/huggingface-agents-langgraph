import { describe, expect, it } from 'vitest';

import { createMemoryServices } from '../../adapters/memory/memoryServices';
import type { Architecture, Catalog } from '../types';
import { toDefinition } from './convert';
import { END, checkInvariants, findNode, type EditorDocument } from './model';
import {
  consistencyDocument,
  documentFromArchitecture,
  plannedDocument,
  verifiedDocument,
} from './templates';

const services = createMemoryServices();
const catalog: Catalog = await services.catalog.getCatalog();
const [summary] = await services.architectures.list();
const builtin: Architecture = await services.architectures.get(summary?.id ?? '');

const ids = (doc: EditorDocument) => doc.graph.nodes.map((node) => node.id);
const direct = (doc: EditorDocument, id: string) => {
  const outgoing = findNode(doc.graph, id)?.outgoing;
  return outgoing?.kind === 'direct' ? outgoing.target : null;
};

describe('the verified V3.1 template', () => {
  const doc = verifiedDocument('verified', catalog, builtin);

  it('is a consistent document that keeps every V3.1 node', () => {
    expect(checkInvariants(doc)).toEqual([]);
    const original = documentFromArchitecture(builtin, catalog, 'x');
    for (const id of ids(original)) expect(ids(doc)).toContain(id);
    expect(ids(doc)).toHaveLength(ids(original).length + 2);
    expect(doc.graph.initialNode).toBe(original.graph.initialNode);
  });

  it('sends the reasoning through a verifier before the answer is produced', () => {
    expect(direct(doc, 'reasoning')).toBe('verify');
    const verify = findNode(doc.graph, 'verify');
    expect(verify?.implementationId).toBe('llm_verifier');
    expect(verify?.params).toEqual({ max_revisions: 1 });
    expect(verify?.outgoing).toEqual({
      kind: 'decision',
      strategy: 'route_on_verdict',
      branches: { accept: 'answer_production', revise: 'revise' },
    });
  });

  it('loops a revision back to the verifier', () => {
    expect(findNode(doc.graph, 'revise')?.implementationId).toBe('llm_reflect');
    expect(direct(doc, 'revise')).toBe('verify');
  });

  it('leaves the rest of the V3.1 wiring as it was', () => {
    const original = documentFromArchitecture(builtin, catalog, 'x');
    for (const id of ids(original).filter((node) => node !== 'reasoning')) {
      expect(findNode(doc.graph, id)?.outgoing).toEqual(findNode(original.graph, id)?.outgoing);
    }
  });

  it('serializes to a definition with the parameters', () => {
    const definition = toDefinition(doc.graph);
    expect(definition.nodes.find((n) => n.id === 'verify')?.params).toEqual({ max_revisions: 1 });
    expect(definition.edges.some((e) => e.type === 'conditional' && e.source === 'verify')).toBe(
      true,
    );
  });

  it('picks fresh ids if the base pipeline already uses these names', () => {
    const first = verifiedDocument('again', catalog, builtin);
    expect(ids(first).filter((id) => id === 'verify')).toHaveLength(1);
  });
});

describe('the plan, tool, reason template', () => {
  const doc = plannedDocument('planned', catalog);

  it('is a consistent document', () => {
    expect(checkInvariants(doc)).toEqual([]);
  });

  it('chains preprocessing, planner, a tool, reasoning and the answer', () => {
    const components = [
      'preprocessing',
      'llm_planner',
      'web_search',
      'reasoning',
      'answer_production',
    ];
    expect(doc.graph.nodes.map((node) => node.implementationId)).toEqual(components);
    const order = ids(doc);
    expect(doc.graph.initialNode).toBe('preprocessing');
    order.slice(0, -1).forEach((id, index) => expect(direct(doc, id)).toBe(order[index + 1]));
    expect(direct(doc, 'answer_production')).toBe(END);
  });
});

describe('the self-consistency template', () => {
  const doc = consistencyDocument('consistent', catalog);

  it('is a consistent document', () => {
    expect(checkInvariants(doc)).toEqual([]);
  });

  it('searches, samples several answers and formats the winner', () => {
    expect(doc.graph.nodes.map((node) => node.implementationId)).toEqual([
      'preprocessing',
      'web_search',
      'self_consistency',
      'answer_production',
    ]);
    expect(findNode(doc.graph, 'vote')?.params).toEqual({ n: 3 });
    expect(direct(doc, 'vote')).toBe('answer_production');
  });
});

describe('templates need their components', () => {
  it('fail clearly when the catalog lacks one', () => {
    const trimmed: Catalog = {
      ...catalog,
      components: catalog.components.filter((c) => c.implementationId !== 'llm_planner'),
    };
    expect(() => plannedDocument('x', trimmed)).toThrow(/llm_planner/);
    expect(() => verifiedDocument('x', { ...trimmed, components: [] }, builtin)).toThrow();
  });
});
