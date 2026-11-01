import '@xyflow/react/dist/style.css';
import '../editor/editor.css';

import { Background, Controls, ReactFlow, ReactFlowProvider } from '@xyflow/react';
import { useMemo } from 'react';

import type { EditorDocument } from '../../domain/editor/model';
import type { Catalog } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { useTheme } from '../../theme/ThemeProvider';
import { nodeTypes } from '../editor/nodes';
import { projectGraph } from '../editor/projection';
import { applyRunOverlay, type RunView } from './overlay';

function Canvas({
  document,
  catalog,
  view,
}: {
  document: EditorDocument;
  catalog: Catalog;
  view: RunView;
}) {
  const { t } = useI18n();
  const { resolved } = useTheme();
  const { nodes, edges } = useMemo(
    () => applyRunOverlay(projectGraph(document, catalog), view),
    [document, catalog, view],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      colorMode={resolved}
      aria-label={t('runs.canvas')}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      minZoom={0.2}
      maxZoom={1.4}
    >
      <Background gap={20} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

/** The architecture of a run, read-only, with the path it took drawn over it. */
export function RunCanvas(props: { document: EditorDocument; catalog: Catalog; view: RunView }) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
