import React from 'react';
import { GitCommit, Sparkles, BookOpen, Layers } from 'lucide-react';

export default function AutodiffViewer({ autodiffSteps = [] }) {
  const rulesReference = [
    {
      op: 'Add(u, v)',
      rule: 'Sum Rule',
      formula: 'du_bar += upstream, dv_bar += upstream',
      note: 'Gradients distribute equally to all addends.',
    },
    {
      op: 'Sub(u, v)',
      rule: 'Difference Rule',
      formula: 'du_bar += upstream, dv_bar -= upstream',
      note: 'Negative upstream adjoint propagated to subtrahend.',
    },
    {
      op: 'Mul(u, v)',
      rule: 'Product Rule',
      formula: 'du_bar += upstream * v, dv_bar += upstream * u',
      note: 'Each argument is scaled by the sibling child and upstream adjoint.',
    },
    {
      op: 'Div(u, v)',
      rule: 'Quotient Rule',
      formula: 'du_bar += upstream / v, dv_bar -= (upstream * u) / (v^2)',
      note: 'Correctly implements division chain rule using existing mul/div nodes.',
    },
    {
      op: 'Pow(u, c)',
      rule: 'Power Rule (Scalar)',
      formula: 'du_bar += upstream * (c * u^(c - 1))',
      note: 'Constant exponents simplified at compile-time.',
    },
    {
      op: 'Pow(u, v)',
      rule: 'General Power Rule',
      formula: 'du_bar += upstream * (v * u^(v-1)), dv_bar += upstream * (u^v * ln(u))',
      note: 'Emits mathematical Log node for variable exponents.',
    },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="overview-container">
        {/* Step-by-step Reverse Propagation Trace */}
        <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', overflow: 'hidden' }}>
          <div
            style={{
              padding: '0.75rem 1rem',
              background: '#161c2c',
              borderBottom: '1px solid #2a354c',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GitCommit size={15} style={{ color: '#f59e0b' }} />
              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f1f5f9' }}>
                REVERSE-MODE ADJOINT ACCUMULATION TRACE
              </span>
            </div>
            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
              Reverse topological pass (root &rarr; parameters)
            </span>
          </div>

          <table className="workbench-table">
            <thead>
              <tr>
                <th style={{ width: '80px' }}>Step #</th>
                <th style={{ width: '120px' }}>Target Node</th>
                <th style={{ width: '100px' }}>Op</th>
                <th style={{ width: '160px' }}>Rule Triggered</th>
                <th>Mathematical Explanation / Adjoint Contribution</th>
              </tr>
            </thead>
            <tbody>
              {autodiffSteps.map((step, idx) => (
                <tr key={idx}>
                  <td style={{ color: '#64748b' }}>#{idx + 1}</td>
                  <td style={{ color: '#38bdf8', fontWeight: 600 }}>{step.name}</td>
                  <td>
                    <span className="badge badge-purple">{step.op}</span>
                  </td>
                  <td>
                    <span className="badge badge-amber">{step.ruleApplied}</span>
                  </td>
                  <td style={{ color: '#cbd5e1' }}>{step.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Compiler Elementary Rules Matrix */}
        <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
            <BookOpen size={16} style={{ color: '#38bdf8' }} />
            <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#f1f5f9' }}>
              GradLang Automatic Differentiation Specification
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.85rem' }}>
            {rulesReference.map((r, i) => (
              <div
                key={i}
                style={{
                  background: '#161c2c',
                  border: '1px solid #1e2638',
                  borderRadius: '6px',
                  padding: '0.85rem 1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#f59e0b', fontSize: '0.85rem' }}>
                    {r.op}
                  </span>
                  <span className="badge badge-cyan">{r.rule}</span>
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: '#34d399', margin: '4px 0' }}>
                  {r.formula}
                </div>
                <p style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{r.note}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
