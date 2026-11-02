import type { ParamSpec, ParamValue } from '../types';

/** Same ceilings as the backend, so an over-long value is refused before it is sent. */
export const MAX_STRING_LENGTH = 200;
export const MAX_TEXT_LENGTH = 4000;

/** Whether `value` is acceptable for the spec: the rules the backend validator enforces. */
export function checkParamValue(spec: ParamSpec, value: unknown): value is ParamValue {
  switch (spec.kind) {
    case 'boolean':
      return typeof value === 'boolean';
    case 'enum':
      return typeof value === 'string' && spec.choices.includes(value);
    case 'string':
    case 'text': {
      const ceiling = spec.kind === 'string' ? MAX_STRING_LENGTH : MAX_TEXT_LENGTH;
      return typeof value === 'string' && value.length <= (spec.maxLength ?? ceiling);
    }
    case 'integer':
    case 'number': {
      if (typeof value !== 'number' || !Number.isFinite(value)) return false;
      if (spec.kind === 'integer' && !Number.isInteger(value)) return false;
      if (spec.minimum !== null && value < spec.minimum) return false;
      if (spec.maximum !== null && value > spec.maximum) return false;
      return true;
    }
  }
}

export type ParamInput = { ok: true; value: ParamValue } | { ok: false };

/** Turn what was typed into a value of the spec's type; an empty number is not a number. */
export function parseParamText(spec: ParamSpec, text: string): ParamInput {
  if (spec.kind === 'integer' || spec.kind === 'number') {
    if (text.trim() === '') return { ok: false };
    const value = Number(text);
    return checkParamValue(spec, value) ? { ok: true, value } : { ok: false };
  }
  return checkParamValue(spec, text) ? { ok: true, value: text } : { ok: false };
}

/** What the node will run with for this parameter: the chosen value, or the default. */
export function effectiveValue(
  spec: ParamSpec,
  explicit: Readonly<Record<string, ParamValue>> | undefined,
): ParamValue | null {
  return explicit?.[spec.name] ?? spec.default;
}

/** `name=value` for the parameters that were set explicitly, at most `limit` of them. */
export function summarizeParams(
  explicit: Readonly<Record<string, ParamValue>> | undefined,
  specs: readonly ParamSpec[],
  limit = 2,
): string[] {
  if (!explicit) return [];
  return specs
    .filter((spec) => explicit[spec.name] !== undefined)
    .slice(0, limit)
    .map((spec) => {
      const value = String(explicit[spec.name]);
      return `${spec.name}=${value.length > 18 ? `${value.slice(0, 17)}…` : value}`;
    });
}
