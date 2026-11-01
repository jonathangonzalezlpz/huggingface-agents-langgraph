import '@xyflow/react/dist/style.css';
import './editor.css';

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useReactFlow,
  type Connection,
  type Edge,
  type NodeChange,
} from '@xyflow/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DragEvent, RefObject } from 'react';

import {
  connect,
  connectBranch,
  disconnect,
  disconnectBranch,
  removeNode,
} from '../../domain/editor/commands';
import { findNode, type EditorDocument, type Point } from '../../domain/editor/model';
import type { Catalog, Diagnostic } from '../../domain/types';
import { useI18n } from '../../i18n/I18nProvider';
import { useTheme } from '../../theme/ThemeProvider';
import { CATEGORY_STYLE } from '../components/categoryStyle';
import { sequence, type EditorAction } from './editorState';
import { nodeTypes } from './nodes';
import { PALETTE_MIME } from './Palette';
import {
  END_ID,
  START_ID,
  branchOfHandle,
  projectGraph,
  type ComponentNodeData,
  type FlowNode,
} from './projection';

/** What the surrounding editor can ask the canvas to do. */
export interface CanvasApi {
  /** The point of the graph at the middle of the visible canvas. */
  centerPosition: () => Point;
  fit: () => void;
  focusNode: (id: string) => void;
}

interface Props {
  doc: EditorDocument;
  catalog: Catalog;
  diagnostics: Diagnostic[];
  readOnly: boolean;
  selectedIds: readonly string[];
  onSelect: (ids: string[]) => void;
  onApply: (action: Extract<EditorAction, { type: 'apply' }>) => void;
  onMove: (positions: Record<string, Point>) => void;
  onAddComponent: (implementationId: string, position: Point) => void;
  apiRef: RefObject<CanvasApi | null>;
}

const round = (point: Point): Point => ({ x: Math.round(point.x), y: Math.round(point.y) });

/** Animated camera moves are skipped for people who ask for reduced motion. */
const motion = (milliseconds: number) =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : milliseconds;

export function EditorCanvas({
  doc,
  catalog,
  diagnostics,
  readOnly,
  selectedIds,
  onSelect,
  onApply,
  onMove,
  onAddComponent,
  apiRef,
}: Props) {
  const { t } = useI18n();
  const { resolved } = useTheme();
  const { fitView, screenToFlowPosition } = useReactFlow();
  const wrapper = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<Record<string, Point>>({});

  const projected = useMemo(
    () => projectGraph(doc, catalog, diagnostics, dragging),
    [doc, catalog, diagnostics, dragging],
  );
  const nodes = useMemo(() => {
    const selected = new Set(selectedIds);
    return projected.nodes.map((node) =>
      selected.has(node.id) ? { ...node, selected: true } : node,
    );
  }, [projected.nodes, selectedIds]);

  useEffect(() => {
    apiRef.current = {
      fit: () => void fitView({ padding: 0.2, duration: motion(250) }),
      focusNode: (id) =>
        void fitView({ nodes: [{ id }], padding: 1.2, maxZoom: 1.1, duration: motion(300) }),
      centerPosition: () => {
        const box = wrapper.current?.getBoundingClientRect();
        return screenToFlowPosition({
          x: (box?.left ?? 0) + (box?.width ?? 0) / 2,
          y: (box?.top ?? 0) + (box?.height ?? 0) / 2,
        });
      },
    };
    return () => {
      apiRef.current = null;
    };
  }, [apiRef, fitView, screenToFlowPosition]);

  const targetName = useCallback(
    (target: string) => (target === END_ID ? t('editor.node.end') : target),
    [t],
  );

  const handleNodesChange = useCallback(
    (changes: NodeChange<FlowNode>[]) => {
      let selection: Set<string> | null = null;
      const moves: Record<string, Point> = {};
      for (const change of changes) {
        if (change.type === 'position' && change.position) moves[change.id] = change.position;
        if (change.type === 'select') {
          selection ??= new Set(selectedIds);
          if (change.selected) selection.add(change.id);
          else selection.delete(change.id);
        }
      }
      if (Object.keys(moves).length > 0) setDragging((current) => ({ ...current, ...moves }));
      if (selection) onSelect([...selection]);
    },
    [onSelect, selectedIds],
  );

  const handleConnect = useCallback(
    ({ source, target, sourceHandle }: Connection) => {
      if (readOnly || source === START_ID) return;
      const branch = branchOfHandle(sourceHandle);
      onApply({
        type: 'apply',
        run: (current) =>
          branch
            ? connectBranch(current, source, branch, target)
            : connect(current, source, target),
        announce: () => ({
          key: 'editor.announce.connected',
          params: { source, target: targetName(target) },
        }),
      });
    },
    [onApply, readOnly, targetName],
  );

  const isValidConnection = useCallback(
    (candidate: Edge | Connection) => {
      const { source, target, sourceHandle } = candidate;
      if (source === START_ID || target === START_ID) return false;
      if (target !== END_ID && !findNode(doc.graph, target)) return false;
      const node = findNode(doc.graph, source);
      if (!node) return false;
      const branch = branchOfHandle(sourceHandle);
      if (node.outgoing.kind === 'decision') {
        return branch !== null && branch in node.outgoing.branches;
      }
      return branch === null;
    },
    [doc.graph],
  );

  const handleEdgesDelete = useCallback(
    (edges: Edge[]) => {
      const steps = edges
        .filter((edge) => edge.source !== START_ID)
        .map((edge) => {
          const branch = branchOfHandle(edge.sourceHandle);
          return (current: EditorDocument) =>
            branch
              ? disconnectBranch(current, edge.source, branch)
              : disconnect(current, edge.source);
        });
      if (steps.length === 0) return;
      onApply({
        type: 'apply',
        run: sequence(...steps),
        announce: () => ({
          key: 'editor.announce.disconnected',
          params: { source: edges[0]?.source ?? '' },
        }),
      });
    },
    [onApply],
  );

  const handleNodesDelete = useCallback(
    (deleted: FlowNode[]) => {
      const ids = deleted.filter((node) => node.type === 'component').map((node) => node.id);
      if (ids.length === 0) return;
      onApply({
        type: 'apply',
        run: sequence(...ids.map((id) => (current: EditorDocument) => removeNode(current, id))),
        announce: () => ({ key: 'editor.announce.removed', params: { id: ids.join(', ') } }),
      });
      onSelect([]);
    },
    [onApply, onSelect],
  );

  const handleDragStop = useCallback(
    (_event: unknown, _node: FlowNode, dragged: FlowNode[]) => {
      const moved = Object.fromEntries(
        dragged
          .filter((node) => node.type === 'component')
          .map((node) => [node.id, round(node.position)]),
      );
      setDragging({});
      if (Object.keys(moved).length > 0) onMove(moved);
    },
    [onMove],
  );

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    const implementationId = event.dataTransfer.getData(PALETTE_MIME);
    if (!implementationId || readOnly) return;
    event.preventDefault();
    onAddComponent(
      implementationId,
      round(screenToFlowPosition({ x: event.clientX, y: event.clientY })),
    );
  };

  return (
    <div
      ref={wrapper}
      className="h-full w-full"
      onDragOver={(event) => {
        if (!readOnly && event.dataTransfer.types.includes(PALETTE_MIME)) {
          event.preventDefault();
          event.dataTransfer.dropEffect = 'copy';
        }
      }}
      onDrop={handleDrop}
    >
      <ReactFlow
        nodes={nodes}
        edges={projected.edges}
        nodeTypes={nodeTypes}
        colorMode={resolved}
        aria-label={t('editor.canvas')}
        onNodesChange={handleNodesChange}
        onConnect={handleConnect}
        isValidConnection={isValidConnection}
        onNodesDelete={handleNodesDelete}
        onEdgesDelete={handleEdgesDelete}
        onNodeDragStop={handleDragStop}
        onNodeClick={(_event, node) => {
          if (node.type === 'component') onSelect([node.id]);
        }}
        onPaneClick={() => onSelect([])}
        nodesConnectable={!readOnly}
        edgesReconnectable={false}
        deleteKeyCode={readOnly ? null : ['Backspace', 'Delete']}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.6}
      >
        <Background gap={20} />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) =>
            node.type === 'component'
              ? CATEGORY_STYLE[(node.data as ComponentNodeData).component?.category ?? 'other']
                  .cssColor
              : 'var(--border-strong)'
          }
        />
      </ReactFlow>
    </div>
  );
}
