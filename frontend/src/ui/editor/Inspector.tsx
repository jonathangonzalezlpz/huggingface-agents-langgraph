import { Trash2 } from 'lucide-react';
import { useId } from 'react';

import { renameArchitecture, renameNode, setDescription } from '../../domain/editor/commands';
import { END, findNode, type EditorDocument } from '../../domain/editor/model';
import type { Catalog, ComponentInfo } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { CATEGORY_STYLE } from '../components/categoryStyle';
import { useComponentDescription } from '../components/componentText';
import { StatusBadge } from '../components/StatusBadge';
import { AvailabilitySection, TextCommitField, type AvailabilityView } from './InspectorFields';

const FIELD = 'min-h-9 w-full rounded-lg border border-line-strong bg-surface px-2 text-sm';
const ACTION =
  'min-h-8 rounded-lg border border-line-strong bg-surface px-2.5 text-xs font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60';

export interface InspectorActions {
  rename: (id: string, newId: string) => void;
  setEntry: (id: string) => void;
  remove: (id: string) => void;
  openConnect: (id: string, branch: string | null) => void;
  disconnect: (id: string, branch: string | null) => void;
  setDecision: (id: string, strategy: string) => void;
  setDescription: (id: string, text: string) => void;
  renameArchitecture: (name: string) => void;
}

function ContractList({ label, items }: { label: string; items: string[] }) {
  const { t } = useI18n();
  return (
    <div>
      <dt className="text-xs font-medium text-fg-muted">{label}</dt>
      <dd className="mt-0.5 flex flex-wrap gap-1">
        {items.length === 0 ? (
          <span className="text-xs text-fg-muted">{t('editor.contract.none')}</span>
        ) : (
          items.map((item) => (
            <code key={item} className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
              {item}
            </code>
          ))
        )}
      </dd>
    </div>
  );
}

function OutputSection({
  doc,
  catalog,
  nodeId,
  readOnly,
  actions,
}: {
  doc: EditorDocument;
  catalog: Catalog;
  nodeId: string;
  readOnly: boolean;
  actions: InspectorActions;
}) {
  const { t } = useI18n();
  const decisionId = useId();
  const node = findNode(doc.graph, nodeId);
  if (!node) return null;
  const { outgoing } = node;
  const name = (target: string) => (target === END ? t('editor.node.end') : target);

  return (
    <section aria-labelledby={`${decisionId}-heading`} className="space-y-3">
      <h3 id={`${decisionId}-heading`} className="text-sm font-semibold">
        {t('editor.node.output')}
      </h3>
      <div>
        <label htmlFor={decisionId} className="mb-1 block text-xs font-medium text-fg-muted">
          {t('editor.node.decision')}
        </label>
        <select
          id={decisionId}
          disabled={readOnly}
          value={outgoing.kind === 'decision' ? outgoing.strategy : ''}
          onChange={(event) => actions.setDecision(nodeId, event.target.value)}
          className={FIELD}
        >
          <option value="">{t('editor.node.decision.none')}</option>
          {catalog.routingStrategies.map((strategy) => (
            <option key={strategy.identifier} value={strategy.identifier}>
              {strategy.identifier}
            </option>
          ))}
        </select>
      </div>

      {outgoing.kind === 'decision' ? (
        <ul className="divide-y divide-line rounded-lg border border-line">
          {Object.entries(outgoing.branches).map(([label, target]) => (
            <li key={label} className="flex items-center gap-2 px-2.5 py-2">
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-medium">{label}</span>
                <span
                  className={`block truncate text-xs ${target === null ? 'text-warning' : 'font-mono text-fg-muted'}`}
                >
                  {target === null ? t('editor.node.pending') : name(target)}
                </span>
              </span>
              <button
                type="button"
                disabled={readOnly}
                onClick={() => actions.openConnect(nodeId, label)}
                className={ACTION}
              >
                {t('editor.node.connect')}
              </button>
              {target !== null && (
                <button
                  type="button"
                  disabled={readOnly}
                  onClick={() => actions.disconnect(nodeId, label)}
                  className={ACTION}
                >
                  {t('editor.node.disconnect')}
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-2">
          <p className="truncate font-mono text-xs text-fg-muted">
            {outgoing.kind === 'direct' ? name(outgoing.target) : t('editor.node.output.none')}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={readOnly}
              onClick={() => actions.openConnect(nodeId, null)}
              className={ACTION}
            >
              {t('editor.node.connect')}
            </button>
            {outgoing.kind === 'direct' && (
              <button
                type="button"
                disabled={readOnly}
                onClick={() => actions.disconnect(nodeId, null)}
                className={ACTION}
              >
                {t('editor.node.disconnect')}
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export function Inspector({
  doc,
  catalog,
  selectedId,
  readOnly,
  actions,
  availability,
}: {
  doc: EditorDocument;
  catalog: Catalog;
  selectedId: string | null;
  readOnly: boolean;
  actions: InspectorActions;
  availability: AvailabilityView;
}) {
  const { t, tp } = useI18n();
  const describe = useComponentDescription();
  const node = selectedId ? findNode(doc.graph, selectedId) : undefined;
  const component: ComponentInfo | undefined = node
    ? catalog.components.find((c) => c.implementationId === node.implementationId)
    : undefined;

  if (!node) {
    return (
      <section aria-labelledby="inspector-title" className="p-4">
        <h2 id="inspector-title" className="text-sm font-semibold">
          {t('editor.inspector')}
        </h2>
        <div className="mt-3 space-y-2">
          <TextCommitField
            label={t('editor.architecture.name')}
            value={doc.graph.architectureId}
            disabled={readOnly}
            mono
            validate={(next) => renameArchitecture(doc, next)}
            onCommit={actions.renameArchitecture}
          />
          <p className="text-sm text-fg-muted">
            {tp('builder.components', doc.graph.nodes.length)}
          </p>
        </div>
        <p className="mt-4 text-sm text-fg-muted">{t('editor.inspector.empty')}</p>
      </section>
    );
  }

  const style = CATEGORY_STYLE[component?.category ?? 'other'];
  const isEntry = doc.graph.initialNode === node.id;

  return (
    <section aria-labelledby="inspector-title" className="space-y-5 p-4">
      <h2 id="inspector-title" className="flex items-center gap-2 text-sm font-semibold">
        <style.Icon aria-hidden="true" className={`size-4 ${style.text}`} />
        {t('editor.inspector')}
      </h2>

      <TextCommitField
        key={`id-${node.id}`}
        label={t('editor.node.id')}
        value={node.id}
        disabled={readOnly}
        mono
        validate={(next) => renameNode(doc, node.id, next)}
        onCommit={(next) => actions.rename(node.id, next)}
      />
      <TextCommitField
        key={`description-${node.id}`}
        label={t('editor.node.description')}
        value={node.description}
        disabled={readOnly}
        multiline
        validate={(next) => setDescription(doc, node.id, next)}
        onCommit={(next) => actions.setDescription(node.id, next)}
      />

      <div>
        <p className="text-xs font-medium text-fg-muted">{t('editor.node.component')}</p>
        <p className="font-mono text-sm">{node.implementationId}</p>
        {component && <p className="mt-0.5 text-xs text-fg-muted">{describe(component)}</p>}
      </div>

      <div>
        {isEntry ? (
          <StatusBadge tone="info">{t('editor.node.isEntry')}</StatusBadge>
        ) : (
          <button
            type="button"
            disabled={readOnly}
            onClick={() => actions.setEntry(node.id)}
            className={ACTION}
          >
            {t('editor.node.setEntry')}
          </button>
        )}
      </div>

      <OutputSection
        doc={doc}
        catalog={catalog}
        nodeId={node.id}
        readOnly={readOnly}
        actions={actions}
      />

      {component && (
        <dl className="space-y-2 border-t border-line pt-4">
          <ContractList
            label={t('editor.contract.requires')}
            items={component.contract.requiredInputs}
          />
          <ContractList
            label={t('editor.contract.optionalInputs')}
            items={component.contract.optionalInputs}
          />
          <ContractList
            label={t('editor.contract.guarantees')}
            items={component.contract.guaranteedOutputs}
          />
          <ContractList
            label={t('editor.contract.optionalOutputs')}
            items={component.contract.optionalOutputs}
          />
        </dl>
      )}

      <AvailabilitySection view={availability} />

      <button
        type="button"
        disabled={readOnly}
        onClick={() => actions.remove(node.id)}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-error px-3 text-sm font-medium text-error hover:bg-error-soft disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Trash2 aria-hidden="true" className="size-4" />
        {t('editor.node.delete')}
      </button>
    </section>
  );
}
