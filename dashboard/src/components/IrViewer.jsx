import React from 'react';

function OptimizationStats({ metrics }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '1rem', margin: '0.75rem 0', fontSize: '0.82rem' }}>
      <span>Pre-optimization: <strong>{metrics.nodesBefore} nodes</strong></span>
      <span>Post-optimization: <strong>{metrics.nodesAfter} nodes</strong></span>
      <span className="badge badge-cyan">
        {metrics.nodeReduction} nodes eliminated ({metrics.percentReduction}% reduction)
      </span>
    </div>
  );
}

export default function IrViewer({ ir }) {
  if (!ir) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No IR listings available.
      </div>
    );
  }

  const { forward, combined } = ir;
  const unchanged = ir.before === ir.after;

  return (
    <div className="overview-container" style={{ flex: 1, minHeight: 0 }}>
      <section aria-label="Forward Computation Optimization" style={{ flexShrink: 0 }}>
        <h3>Forward Computation Optimization</h3>
        <OptimizationStats metrics={forward} />
        {unchanged && (
          <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
            {combined.nodeReduction > 0
              ? 'No optimization changes were required for the forward computation. The measured reduction occurred in the derivative graphs.'
              : 'No optimization changes were required for the forward computation or derivative graphs.'}
          </p>
        )}
        <div className="diff-grid" style={{ padding: '1rem 0', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))' }}>
          <div className="diff-col">
            <div className="diff-header">
              <span>Original Forward IR</span>
              <span className="badge badge-amber">{forward.nodesBefore} nodes</span>
            </div>
            <div className="diff-body" style={{ maxHeight: '55vh' }}>
              {ir.before || '# Empty graph'}
            </div>
          </div>
          <div className="diff-col">
            <div className="diff-header">
              <span>Optimized Forward IR</span>
              <span className="badge badge-cyan">{forward.nodesAfter} nodes</span>
            </div>
            <div className="diff-body" style={{ maxHeight: '55vh' }}>
              {ir.after || '# Empty graph'}
            </div>
          </div>
        </div>
      </section>
      <section aria-label="Combined Forward + Gradient Optimization" style={{ flexShrink: 0 }}>
        <h3>Combined Forward + Gradient Optimization</h3>
        <OptimizationStats metrics={combined} />
        <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
          These statistics include the forward computation and all automatic differentiation graphs.
          Each unique reachable node is counted once, including computations shared across graphs.
          The IR listings above show only the forward computation.
        </p>
      </section>
    </div>
  );
}
