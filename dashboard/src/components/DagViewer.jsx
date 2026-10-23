import React, { useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { Layers } from 'lucide-react';
import { formatDagValue } from '../dagFormatting';

/**
 * Custom node renderer supporting operations, constants, variables,
 * root outputs, and shared computation highlights.
 */
function CustomDagNode({ data }) {
  const { label, kind, isShared, isRoot, rootName, rootNames, consumerCount, evaluatedValue } = data;
  const isGradientRoot = rootNames?.some((name) => name.startsWith('d/d'));

  let nodeClass = 'custom-dag-node';
  if (isRoot) nodeClass += ' node-root';
  else if (kind === 'var') nodeClass += ' node-var';
  else if (kind === 'const') nodeClass += ' node-const';
  else nodeClass += ' node-op';

  if (isShared) nodeClass += ' node-shared';

  return (
    <div className={nodeClass} title={`${label}: ${formatDagValue(evaluatedValue)}`}>
      <Handle type="target" position={Position.Top} style={{ background: '#38bdf8' }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
          <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{label}</span>
          {consumerCount > 1 && (
            <span style={{ fontSize: '0.65rem', background: '#f59e0b', color: '#000', padding: '1px 4px', borderRadius: '3px', fontWeight: 800 }}>
              SHARED ×{consumerCount}
            </span>
          )}
        </div>
        <span className="dag-node-value">
          {isRoot ? (isGradientRoot ? 'Gradient' : 'Output') : 'Value'} = {formatDagValue(evaluatedValue)}
        </span>
        {rootName && (
          <span className="dag-node-root" title={rootName}>
            {rootName}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#38bdf8' }} />
    </div>
  );
}

const nodeTypes = {
  customNode: CustomDagNode,
};

function layoutGraph(rawNodes, rawEdges, direction = 'TB') {
  if (!rawNodes || rawNodes.length === 0) return { nodes: [], edges: [] };

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 60, ranksep: 75 });

  rawNodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 210, height: 76 });
  });

  rawEdges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const nodes = rawNodes.map((node) => {
    const pos = dagreGraph.node(node.id) || { x: 0, y: 0 };
    return {
      id: node.id,
      type: 'customNode',
      position: { x: pos.x - 105, y: pos.y - 38 },
      ariaLabel: `${node.label}: value ${formatDagValue(node.evaluatedValue)}${node.isRoot ? `; ${node.rootName}` : ''}`,
      data: node,
    };
  });

  const edges = rawEdges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: edge.source.includes('opt') || false,
    style: { stroke: '#38bdf8', strokeWidth: 1.8 },
  }));

  return { nodes, edges };
}

export default function DagViewer({ dags, parameters = [], evaluatedInputs = {}, loading = false, error = null }) {
  const [activeView, setActiveView] = useState('combined');
  const view = activeView.startsWith('grad_') && !dags?.derivatives?.[activeView.slice(5)]
    ? 'combined' : activeView;

  // Pick graph based on active view
  const currentDagData = useMemo(() => {
    if (!dags) return null;
    if (view === 'combined') return dags.combined;
    if (view === 'forwardOpt') return dags.forwardOpt;
    if (view === 'forwardRaw') return dags.forwardRaw;
    if (view.startsWith('grad_')) {
      const param = view.slice(5);
      return dags.derivatives?.[param] || null;
    }
    return dags.combined;
  }, [dags, view]);

  const { nodes, edges } = useMemo(() => {
    if (!currentDagData) return { nodes: [], edges: [] };
    return layoutGraph(currentDagData.nodes || [], currentDagData.edges || []);
  }, [currentDagData]);

  if (!dags) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No DAG data available. Compile a program to view the intermediate graph.
      </div>
    );
  }

  return (
    <div className="dag-container">
      {/* DAG Sub-Navigation */}
      <div className="dag-toolbar">
        <div className="dag-selector">
          <button
            className={`dag-btn ${view === 'combined' ? 'active' : ''}`}
            onClick={() => setActiveView('combined')}
          >
            <Layers size={13} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            Combined (Forward + Derivatives, Optimized)
          </button>
          <button
            className={`dag-btn ${view === 'forwardOpt' ? 'active' : ''}`}
            onClick={() => setActiveView('forwardOpt')}
          >
            Forward (Optimized)
          </button>
          <button
            className={`dag-btn ${view === 'forwardRaw' ? 'active' : ''}`}
            onClick={() => setActiveView('forwardRaw')}
          >
            Forward (Pre-Opt)
          </button>
          {parameters.map((p) => (
            <button
              key={p}
              className={`dag-btn ${view === `grad_${p}` ? 'active' : ''}`}
              onClick={() => setActiveView(`grad_${p}`)}
            >
              d/d{p} (Optimized)
            </button>
          ))}
        </div>

        {/* Legend */}
        <div className="dag-legend">
          <span>{nodes.length} unique nodes in selected graph</span>
          <div className="legend-item">
            <span className="legend-dot var"></span>
            <span>Var</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot const"></span>
            <span>Const</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot op"></span>
            <span>Op</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot root"></span>
            <span>Output Root</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot shared"></span>
            <span>Shared (Multiple Input Uses)</span>
          </div>
        </div>
      </div>

      <div className="dag-evaluation-status" role="status">
        {loading ? 'Evaluating updated program and inputs...' : error
          ? 'Compilation failed. Showing the last successful evaluation.'
          : 'Evaluated inputs: ' + (Object.entries(evaluatedInputs).map(([name, value]) => `${name} = ${formatDagValue(value)}`).join(', ') || 'constant program')}
        <span> · Values refresh automatically while this tab is open.</span>
      </div>
      <div className="dag-workspace">
      <div className="dag-canvas">
        <ReactFlow
          key={view}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          attributionPosition="bottom-left"
          minZoom={0.2}
          maxZoom={2.5}
        >
          <Background color="#1e293b" gap={20} size={1} />
          <Controls style={{ background: '#101420', border: '1px solid #2a354c', fill: '#94a3b8' }} />
          <MiniMap
            style={{ background: '#090c12', border: '1px solid #2a354c', width: 140, height: 90 }}
            nodeColor={(n) => {
              if (n.data?.isShared) return '#f59e0b';
              if (n.data?.isRoot) return '#10b981';
              if (n.data?.kind === 'var') return '#38bdf8';
              if (n.data?.kind === 'const') return '#a855f7';
              return '#60a5fa';
            }}
          />
        </ReactFlow>

      </div>
      </div>
    </div>
  );
}
