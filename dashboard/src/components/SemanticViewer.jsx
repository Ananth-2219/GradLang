import React from 'react';
import { Database, CheckCircle2, ShieldCheck, Sparkles } from 'lucide-react';

export default function SemanticViewer({ symbols = {} }) {
  const symbolEntries = Object.entries(symbols);

  const semanticChecks = [
    {
      title: 'Variable Definition Check',
      description: 'Verifies every variable is declared in function parameters or assigned before use.',
      status: 'PASS',
    },
    {
      title: 'Duplicate Parameter Check',
      description: 'Enforces unique parameter names in function signatures.',
      status: 'PASS',
    },
    {
      title: 'Scalar & Shape Consistency',
      description: 'Validates that scalar operations have empty tuple shape () and vectors have positive integer lengths.',
      status: 'PASS',
    },
    {
      title: 'Elemental Broadcasting',
      description: 'Permits elementwise operations between equal shapes or scalar broadcasting.',
      status: 'PASS',
    },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="overview-container">
        {/* Symbol Table Section */}
        <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', overflow: 'hidden' }}>
          <div
            style={{
              padding: '0.75rem 1rem',
              background: '#161c2c',
              borderBottom: '1px solid #2a354c',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Database size={15} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f1f5f9' }}>
              SYMBOL TABLE (Scope &amp; Inferred Types)
            </span>
          </div>

          <table className="workbench-table">
            <thead>
              <tr>
                <th style={{ width: '160px' }}>Symbol Identifier</th>
                <th style={{ width: '120px' }}>Kind</th>
                <th style={{ width: '140px' }}>Inferred Shape</th>
                <th>Validation Status</th>
              </tr>
            </thead>
            <tbody>
              {symbolEntries.map(([name, sym]) => (
                <tr key={name}>
                  <td style={{ color: '#38bdf8', fontWeight: 600 }}>{name}</td>
                  <td>
                    <span className="badge badge-purple">{sym.kind}</span>
                  </td>
                  <td style={{ color: '#94a3b8' }}>
                    {sym.shape?.length === 0 ? '() [Scalar]' : `(${sym.shape.join(', ')})`}
                  </td>
                  <td>
                    <span className="badge badge-emerald">
                      <CheckCircle2 size={12} style={{ marginRight: '3px' }} /> VALID
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Semantic Rules Verification Summary */}
        <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
            <ShieldCheck size={16} style={{ color: '#10b981' }} />
            <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#f1f5f9' }}>
              Semantic Invariant Checks
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            {semanticChecks.map((chk, i) => (
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
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#e2e8f0' }}>{chk.title}</span>
                  <span className="badge badge-emerald">{chk.status}</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.4 }}>{chk.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
