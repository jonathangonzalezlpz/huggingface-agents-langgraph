import { describe, expect, it } from 'vitest';

import type { Catalog, ParamSpec } from '../types';
import { setParam } from './commands';
import { fromDefinition, toDefinition } from './convert';
import type { EditorDocument } from './model';
import { checkParamValue, effectiveValue, parseParamText, summarizeParams } from './params';

const spec = (over: Partial<ParamSpec> & Pick<ParamSpec, 'name' | 'kind'>): ParamSpec => ({
  default: null,
  required: false,
  minimum: null,
  maximum: null,
  maxLength: null,
  choices: [],
  ...over,
});

const count = spec({ name: 'n', kind: 'integer', default: 2, minimum: 1, maximum: 9 });
const temperature = spec({ name: 't', kind: 'number', default: 0.5, minimum: 0, maximum: 2 });
const flag = spec({ name: 'flag', kind: 'boolean', default: false });
const mode = spec({ name: 'mode', kind: 'enum', default: 'fast', choices: ['fast', 'slow'] });
const label = spec({ name: 'label', kind: 'string', default: '', maxLength: 5 });
const prompt = spec({ name: 'prompt', kind: 'text', default: '', maxLength: 10 });

describe('checking a value against its spec', () => {
  it.each([
    [count, 3, true],
    [count, 0, false],
    [count, 10, false],
    [count, 2.5, false],
    [count, '3', false],
    [count, true, false],
    [temperature, 1.5, true],
    [temperature, Number.NaN, false],
    [temperature, Infinity, false],
    [flag, true, true],
    [flag, 1, false],
    [mode, 'slow', true],
    [mode, 'other', false],
    [label, 'abc', true],
    [label, 'abcdef', false],
    [label, 3, false],
    [prompt, 'x'.repeat(10), true],
    [prompt, 'x'.repeat(11), false],
  ])('%o accepts %j: %s', (param, value, expected) => {
    expect(checkParamValue(param, value)).toBe(expected);
  });

  it('applies the backend ceilings when a text has no limit of its own', () => {
    expect(checkParamValue(spec({ name: 's', kind: 'string' }), 'x'.repeat(200))).toBe(true);
    expect(checkParamValue(spec({ name: 's', kind: 'string' }), 'x'.repeat(201))).toBe(false);
    expect(checkParamValue(spec({ name: 'p', kind: 'text' }), 'x'.repeat(4000))).toBe(true);
    expect(checkParamValue(spec({ name: 'p', kind: 'text' }), 'x'.repeat(4001))).toBe(false);
  });
});

describe('reading what was typed', () => {
  it('turns numeric text into numbers and refuses an empty or invalid one', () => {
    expect(parseParamText(count, '4')).toEqual({ ok: true, value: 4 });
    expect(parseParamText(count, ' 4 ')).toEqual({ ok: true, value: 4 });
    expect(parseParamText(count, '')).toEqual({ ok: false });
    expect(parseParamText(count, 'four')).toEqual({ ok: false });
    expect(parseParamText(count, '20')).toEqual({ ok: false });
    expect(parseParamText(temperature, '0.25')).toEqual({ ok: true, value: 0.25 });
  });

  it('keeps text as it is, empty included', () => {
    expect(parseParamText(label, '')).toEqual({ ok: true, value: '' });
    expect(parseParamText(label, 'abcdef')).toEqual({ ok: false });
  });
});

describe('what a node runs with', () => {
  it('is the explicit value, or the default', () => {
    expect(effectiveValue(count, { n: 7 })).toBe(7);
    expect(effectiveValue(count, {})).toBe(2);
    expect(effectiveValue(count, undefined)).toBe(2);
  });

  it('summarizes only the parameters that were set, shortening long values', () => {
    expect(summarizeParams(undefined, [count])).toEqual([]);
    expect(summarizeParams({ n: 3 }, [count, mode])).toEqual(['n=3']);
    expect(summarizeParams({ n: 3, mode: 'slow', flag: true }, [count, mode, flag])).toEqual([
      'n=3',
      'mode=slow',
    ]);
    expect(summarizeParams({ prompt: 'x'.repeat(30) }, [prompt])[0]).toBe(
      `prompt=${'x'.repeat(17)}…`,
    );
  });
});

const catalog: Catalog = {
  categories: ['other'],
  components: [
    {
      implementationId: 'tunable',
      description: '',
      category: 'other',
      recoverErrors: false,
      contract: {
        requiredInputs: ['question'],
        optionalInputs: [],
        guaranteedOutputs: ['draft_answer'],
        optionalOutputs: [],
      },
      params: [count, mode, label],
    },
    {
      implementationId: 'plain',
      description: '',
      category: 'other',
      recoverErrors: false,
      contract: {
        requiredInputs: [],
        optionalInputs: [],
        guaranteedOutputs: [],
        optionalOutputs: [],
      },
      params: [],
    },
  ],
  routingStrategies: [],
  state: { types: ['AgentState'], fields: ['question'], initialFields: ['question'] },
};

const doc = (nodes: EditorDocument['graph']['nodes']): EditorDocument => ({
  graph: {
    architectureId: 'a',
    schemaVersion: '4.0',
    stateType: 'AgentState',
    initialNode: nodes[0]?.id ?? null,
    nodes,
  },
  layout: Object.fromEntries(nodes.map((node) => [node.id, { x: 0, y: 0 }])),
});

const tunable = doc([
  { id: 't', implementationId: 'tunable', description: '', outgoing: { kind: 'none' } },
  { id: 'p', implementationId: 'plain', description: '', outgoing: { kind: 'none' } },
]);

describe('setParam command', () => {
  it('sets a valid value on the node', () => {
    const result = setParam(tunable, catalog, 't', 'n', 5);
    expect(result.ok && result.doc.graph.nodes[0]?.params).toEqual({ n: 5 });
  });

  it('keeps the other parameters when one changes', () => {
    const first = setParam(tunable, catalog, 't', 'n', 5);
    if (!first.ok) throw new Error('unexpected');
    const second = setParam(first.doc, catalog, 't', 'mode', 'slow');
    expect(second.ok && second.doc.graph.nodes[0]?.params).toEqual({ n: 5, mode: 'slow' });
  });

  it('returns the same document when nothing changes', () => {
    const first = setParam(tunable, catalog, 't', 'n', 5);
    if (!first.ok) throw new Error('unexpected');
    const again = setParam(first.doc, catalog, 't', 'n', 5);
    expect(again.ok && again.doc).toBe(first.doc);
    const resetAbsent = setParam(tunable, catalog, 't', 'n', null);
    expect(resetAbsent.ok && resetAbsent.doc).toBe(tunable);
  });

  it('returns a parameter to its default and drops the empty set', () => {
    const first = setParam(tunable, catalog, 't', 'n', 5);
    if (!first.ok) throw new Error('unexpected');
    const reset = setParam(first.doc, catalog, 't', 'n', null);
    expect(reset.ok && reset.doc.graph.nodes[0]).not.toHaveProperty('params');
  });

  it.each([
    [{ name: 'n', value: 99 }, 'invalid-param'],
    [{ name: 'mode', value: 'other' }, 'invalid-param'],
    [{ name: 'label', value: 'too long!' }, 'invalid-param'],
    [{ name: 'color', value: 'red' }, 'unknown-param'],
  ])('refuses %o as %s', ({ name, value }, code) => {
    const result = setParam(tunable, catalog, 't', name, value);
    expect(result.ok).toBe(false);
    expect(!result.ok && result.reason).toEqual({ code, subject: name });
  });

  it('refuses a node that does not exist, and parameters on a component without any', () => {
    expect(setParam(tunable, catalog, 'zzz', 'n', 1)).toMatchObject({
      ok: false,
      reason: { code: 'unknown-node' },
    });
    expect(setParam(tunable, catalog, 'p', 'n', 1)).toMatchObject({
      ok: false,
      reason: { code: 'unknown-param' },
    });
  });
});

describe('definitions and parameters', () => {
  it('writes params only when some were set, so saved versions keep their content', () => {
    const plain = toDefinition(tunable.graph);
    expect(plain.nodes[0]).not.toHaveProperty('params');
    const set = setParam(tunable, catalog, 't', 'n', 4);
    if (!set.ok) throw new Error('unexpected');
    expect(toDefinition(set.doc.graph).nodes[0]?.params).toEqual({ n: 4 });
  });

  it('reads them back from a stored definition', () => {
    const set = setParam(tunable, catalog, 't', 'label', 'hi');
    if (!set.ok) throw new Error('unexpected');
    const { graph, issues } = fromDefinition(toDefinition(set.doc.graph), catalog);
    expect(issues).toEqual([]);
    expect(graph.nodes[0]?.params).toEqual({ label: 'hi' });
    expect(graph.nodes[1]).not.toHaveProperty('params');
  });
});
