import React from 'react';
import { Cpu, Zap, Activity, CheckCircle2, TrendingDown, Clock } from 'lucide-react';

export default function OverviewPanel({ data }) {
  if (!data || !data.success) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No compilation results yet. Click "Compile & Run Pipeline" to analyze the code.
      </div>
    );
  }

  const { ir, execution, compileTimeMs, parameters } = data;
  const output = execution?.output;
  const gradients = execution?.gradients || {};

  return (
    <div className="overview-container">
      {/* Top Telemetry Cards */}
      <div className="metrics-grid">
        {/* Output Value */}
        <div className="metric-card emerald">
          <span className="metric-title">Forward Evaluation f(x)</span>
          <span className="metric-value">
            {output !== null && output !== undefined ? Number(output).toFixed(6) : 'N/A'}
          </span>
          <span className="metric-sub">Computed by generated forward Python code</span>
        </div>

        {/* Node Count Reduction */}
        <div className="metric-card cyan">
          <span className="metric-title">Optimization Efficiency</span>
          <span className="metric-value">
            {ir.nodeReduction > 0 ? `-${ir.percentReduction}%` : '0%'}
          </span>
          <span className="metric-sub">
            {ir.nodesBefore} IR nodes &rarr; {ir.nodesAfter} nodes ({ir.nodeReduction} eliminated)
          </span>
        </div>

        {/* Compilation Latency */}
        <div className="metric-card amber">
          <span className="metric-title">Total Compile Latency</span>
          <span className="metric-value">{compileTimeMs} ms</span>
          <span className="metric-sub">End-to-end lexing through code execution</span>
        </div>

        {/* Pipeline Status */}
        <div className="metric-card purple">
          <span className="metric-title">Compiler Status</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <CheckCircle2 size={24} style={{ color: '#10b981' }} />
            <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f1f5f9' }}>PASSED</span>
          </div>
          <span className="metric-sub">All 7 compiler passes completed</span>
        </div>
      </div>

      {/* Analytical Gradients Section */}
      <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap size={16} style={{ color: '#f59e0b' }} />
            <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#f1f5f9' }}>
              Reverse-Mode Analytical Gradients (&nabla;f)
            </h3>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
            Computed in single reverse pass via topological adjoints
          </span>
        </div>

        {parameters && parameters.length > 0 ? (
          <div className="gradients-grid">
            {parameters.map((param) => {
              const val = gradients[param];
              return (
                <div key={param} className="gradient-card">
                  <span className="grad-label">&part;f / &part;{param}</span>
                  <span className="grad-value">
                    {val !== undefined && val !== null ? Number(val).toFixed(6) : 'N/A'}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: '0.8rem' }}>No parameter gradients available.</div>
        )}
      </div>

      {/* Compiler Optimization Breakdown */}
      <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.75rem' }}>
          <TrendingDown size={16} style={{ color: '#38bdf8' }} />
          <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#f1f5f9' }}>
            IR Graph Reductions (CSE &amp; Constant Folding)
          </h3>
        </div>
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '1rem' }}>
          GradLang uses structural hash interning for Common Subexpression Elimination (CSE) across both forward
          and backward passes, and constant folds arithmetic expressions at compile time.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
          <div style={{ background: '#161c2c', padding: '0.75rem 1rem', borderRadius: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Raw IR Nodes</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: '#e2e8f0' }}>{ir.nodesBefore}</div>
          </div>
          <div style={{ background: '#161c2c', padding: '0.75rem 1rem', borderRadius: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Optimized Nodes</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: '#38bdf8' }}>{ir.nodesAfter}</div>
          </div>
          <div style={{ background: '#161c2c', padding: '0.75rem 1rem', borderRadius: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Nodes Eliminated</span>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: '#10b981' }}>{ir.nodeReduction}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
