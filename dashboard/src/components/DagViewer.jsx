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
import { Share2, Network, Eye, Layers } from 'lucide-react';

/**
 * Custom node renderer supporting operations, constants, variables,
 * root outputs, and shared computation highlights.
 */
function CustomDagNode({ data }) {
  const { label, op, value, kind, isShared, isRoot, rootName, consumerCount } = data;

  let nodeClass = 'custom-dag-node';
  if (isRoot) nodeClass += ' node-root';
  else if (kind === 'var') nodeClass += ' node-var';
  else if (kind === 'const') nodeClass += ' node-const';
  else nodeClass += ' node-op';

  if (isShared) nodeClass += ' node-shared';

  return (
    <div className={nodeClass}>
      <Handle type="target" position={Position.Top} style={{ background: '#38bdf8' }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
          <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{op}</span>
          {consumerCount > 1 && (
            <span style={{ fontSize: '0.65rem', background: '#f59e0b', color: '#000', padding: '1px 4px', borderRadius: '3px', fontWeight: 800 }}>
              x{consumerCount}
            </span>
          )}
        </div>
        {value !== null && value !== undefined && (
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
            val: {String(value)}
          </span>
        )}
        {rootName && (
          <span style={{ fontSize: '0.7rem', color: '#34d399', fontWeight: 600 }}>
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
    dagreGraph.setNode(node.id, { width: 140, height: 60 });
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
      position: { x: pos.x - 70, y: pos.y - 30 },
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

export default function DagViewer({ dags, parameters = [] }) {
  const [activeView, setActiveView] = useState('combined');
  const [selectedNode, setSelectedNode] = useState(null);

  // Pick graph based on active view
  const currentDagData = useMemo(() => {
    if (!dags) return null;
    if (activeView === 'combined') return dags.combined;
    if (activeView === 'forwardOpt') return dags.forwardOpt;
    if (activeView === 'forwardRaw') return dags.forwardRaw;
    if (activeView.startsWith('grad_')) {
      const param = activeView.replace('grad_', '');
      return dags.derivatives?.[param] || null;
    }
    return dags.combined;
  }, [dags, activeView]);

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
            className={`dag-btn ${activeView === 'combined' ? 'active' : ''}`}
            onClick={() => { setActiveView('combined'); setSelectedNode(null); }}
          >
            <Layers size={13} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            Combined (Forward + Derivatives, Optimized)
          </button>
          <button
            className={`dag-btn ${activeView === 'forwardOpt' ? 'active' : ''}`}
            onClick={() => { setActiveView('forwardOpt'); setSelectedNode(null); }}
          >
            Forward (Optimized)
          </button>
          <button
            className={`dag-btn ${activeView === 'forwardRaw' ? 'active' : ''}`}
            onClick={() => { setActiveView('forwardRaw'); setSelectedNode(null); }}
          >
            Forward (Pre-Opt)
          </button>
          {parameters.map((p) => (
            <button
              key={p}
              className={`dag-btn ${activeView === `grad_${p}` ? 'active' : ''}`}
              onClick={() => { setActiveView(`grad_${p}`); setSelectedNode(null); }}
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
            <span>Shared (Multiple Consumers)</span>
          </div>
        </div>
      </div>

      {/* Main Flow Canvas */}
      <div style={{ flex: 1, position: 'relative' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => setSelectedNode(node.data)}
          fitView
          attributionPosition="bottom-left"
          minZoom={0.2}
          maxZoom={2.5}
        >
          <Background color="#1e293b" gap={20} size={1} />
          <Controls style={{ background: '#101420', border: '1px solid #2a354c', fill: '#94a3b8' }} />
          <MiniMap
            style={{ background: '#090c12', border: '1px solid #2a354c' }}
            nodeColor={(n) => {
              if (n.data?.isShared) return '#f59e0b';
              if (n.data?.isRoot) return '#10b981';
              if (n.data?.kind === 'var') return '#38bdf8';
              if (n.data?.kind === 'const') return '#a855f7';
              return '#60a5fa';
            }}
          />
        </ReactFlow>

        {/* Node Detail Inspector Drawer */}
        {selectedNode && (
          <div
            style={{
              position: 'absolute',
              bottom: 16,
              right: 16,
              width: 280,
              background: '#101420',
              border: '1px solid #2a354c',
              borderRadius: '8px',
              padding: '12px 16px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
              zIndex: 30,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontWeight: 700, color: '#38bdf8', fontSize: '0.88rem' }}>Node Inspector</span>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '1rem' }}
              >
                &times;
              </button>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div><strong>ID:</strong> <span style={{ fontFamily: 'monospace' }}>{selectedNode.id}</span></div>
              <div><strong>Operation:</strong> <span style={{ fontFamily: 'monospace', color: '#a855f7' }}>{selectedNode.op}</span></div>
              {selectedNode.value !== null && (
                <div><strong>Value:</strong> <span style={{ fontFamily: 'monospace' }}>{String(selectedNode.value)}</span></div>
              )}
              <div><strong>Consumers (out-degree):</strong> {selectedNode.consumerCount}</div>
              <div><strong>Shared Computation:</strong> {selectedNode.isShared ? <span style={{ color: '#f59e0b', fontWeight: 600 }}>YES (Reused in DAG)</span> : 'No'}</div>
              {selectedNode.rootName && (
                <div><strong>Root Role:</strong> <span style={{ color: '#10b981' }}>{selectedNode.rootName}</span></div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
