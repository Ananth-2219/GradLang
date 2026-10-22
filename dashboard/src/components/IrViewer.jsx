import React from 'react';
import { ArrowRight, Layers, Cpu, Minimize2 } from 'lucide-react';

export default function IrViewer({ ir }) {
  if (!ir) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No IR listings available.
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top Telemetry Header */}
      <div
        style={{
          padding: '0.75rem 1.25rem',
          background: '#0f1420',
          borderBottom: '1px solid #2a354c',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PRE-OPT NODES:</span>
            <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#f1f5f9' }}>{ir.nodesBefore}</span>
          </div>
          <ArrowRight size={14} color="#64748b" />
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>POST-OPT NODES:</span>
            <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#38bdf8' }}>{ir.nodesAfter}</span>
          </div>
          <span className="badge badge-emerald">
            {ir.nodeReduction} ELIMINATED (-{ir.percentReduction}%)
          </span>
        </div>

        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
          Topological 3-address linear instructions
        </span>
      </div>

      {/* Side-by-Side IR Code Blocks */}
      <div className="diff-grid">
        {/* Pre-Opt Column */}
        <div className="diff-col">
          <div className="diff-header">
            <span>RAW FORWARD IR (PRE-OPTIMIZATION)</span>
            <span className="badge badge-amber">{ir.nodesBefore} nodes</span>
          </div>
          <div className="diff-body">
            {ir.before || '# Empty graph'}
          </div>
        </div>

        {/* Post-Opt Column */}
        <div className="diff-col">
          <div className="diff-header">
            <span>OPTIMIZED IR (POST-FOLDING &amp; CSE)</span>
            <span className="badge badge-cyan">{ir.nodesAfter} nodes</span>
          </div>
          <div className="diff-body">
            {ir.after || '# Empty graph'}
          </div>
        </div>
      </div>
    </div>
  );
}
