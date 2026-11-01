import { useId } from 'react';

import { setParam, type CommandResult } from '../../domain/editor/commands';
import type { EditorDocument, EditorNode } from '../../domain/editor/model';
import { effectiveValue, parseParamText } from '../../domain/editor/params';
import type { Catalog, ComponentInfo, ParamSpec, ParamValue } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { useParamLabel } from '../components/componentText';
import { TextCommitField } from './InspectorFields';

const FIELD = 'w-full rounded-lg border border-line-strong bg-surface px-2 text-sm';
const ACTION =
  'min-h-8 rounded-lg border border-line-strong px-2.5 text-xs font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60';

type SetParam = (id: string, name: string, value: ParamValue | null) => void;

const refused = (name: string): CommandResult => ({
  ok: false,
  reason: { code: 'invalid-param', subject: name },
});

function Meta({ spec }: { spec: ParamSpec }) {
  const { t } = useI18n();
  const shown = spec.default === null ? t('editor.params.none') : String(spec.default);
  return (
    <p className="mt-1 text-xs text-fg-muted">
      {t('editor.params.default', { value: shown })}
      {spec.required && ` · ${t('editor.params.required')}`}
    </p>
  );
}

function ParamField({
  doc,
  catalog,
  node,
  spec,
  readOnly,
  onSet,
}: {
  doc: EditorDocument;
  catalog: Catalog;
  node: EditorNode;
  spec: ParamSpec;
  readOnly: boolean;
  onSet: SetParam;
}) {
  const { t } = useI18n();
  const label = useParamLabel()(node.implementationId, spec.name);
  const id = useId();
  const explicit = node.params?.[spec.name];
  const value = effectiveValue(spec, node.params);
  const reset = (
    <button
      type="button"
      disabled={readOnly}
      onClick={() => onSet(node.id, spec.name, null)}
      className={ACTION}
    >
      {t('editor.params.reset')}
    </button>
  );

  let control: React.ReactNode;
  if (spec.kind === 'boolean') {
    control = (
      <label className="inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          disabled={readOnly}
          checked={value === true}
          onChange={(event) => onSet(node.id, spec.name, event.target.checked)}
        />
        {label}
      </label>
    );
  } else if (spec.kind === 'enum') {
    control = (
      <div>
        <label htmlFor={id} className="mb-1 block text-xs font-medium text-fg-muted">
          {label}
        </label>
        <select
          id={id}
          disabled={readOnly}
          value={typeof explicit === 'string' ? explicit : ''}
          onChange={(event) => onSet(node.id, spec.name, event.target.value || null)}
          className={FIELD}
        >
          <option value="">
            {spec.default === null
              ? t('editor.params.none')
              : t('editor.params.defaultOption', { value: String(spec.default) })}
          </option>
          {spec.choices.map((choice) => (
            <option key={choice} value={choice}>
              {choice}
            </option>
          ))}
        </select>
      </div>
    );
  } else {
    control = (
      <TextCommitField
        key={`${node.id}-${spec.name}-${String(explicit ?? '')}`}
        label={label}
        value={value === null ? '' : String(value)}
        disabled={readOnly}
        multiline={spec.kind === 'text'}
        mono={spec.kind === 'integer' || spec.kind === 'number'}
        validate={(next) => {
          const parsed = parseParamText(spec, next);
          return parsed.ok
            ? setParam(doc, catalog, node.id, spec.name, parsed.value)
            : refused(spec.name);
        }}
        onCommit={(next) => {
          const parsed = parseParamText(spec, next);
          if (parsed.ok) onSet(node.id, spec.name, parsed.value);
        }}
      />
    );
  }

  return (
    <li className="space-y-1">
      {control}
      <div className="flex items-start justify-between gap-2">
        <Meta spec={spec} />
        {explicit !== undefined && reset}
      </div>
    </li>
  );
}

/** One control per parameter the component declares, built from the catalog's specs. */
export function ParamsSection({
  doc,
  catalog,
  node,
  component,
  readOnly,
  onSet,
}: {
  doc: EditorDocument;
  catalog: Catalog;
  node: EditorNode;
  component: ComponentInfo;
  readOnly: boolean;
  onSet: SetParam;
}) {
  const { t } = useI18n();
  const headingId = useId();
  if (component.params.length === 0) return null;
  return (
    <section aria-labelledby={headingId} className="space-y-3 border-t border-line pt-4">
      <h3 id={headingId} className="text-sm font-semibold">
        {t('editor.params')}
      </h3>
      <ul className="space-y-4">
        {component.params.map((spec) => (
          <ParamField
            key={spec.name}
            doc={doc}
            catalog={catalog}
            node={node}
            spec={spec}
            readOnly={readOnly}
            onSet={onSet}
          />
        ))}
      </ul>
    </section>
  );
}
