import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, RefreshCw, Calculator } from 'lucide-react';

export default function ValidationViewer({ finiteDifferences, onRevalidate, epsilon, setEpsilon }) {
  if (!finiteDifferences) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No finite-difference validation data available. Provide inputs and compile to validate gradients.
      </div>
    );
  }

  const entries = Object.entries(finiteDifferences).filter(([k]) => k !== 'error');
  const hasError = finiteDifferences.error;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Controls Bar */}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Calculator size={15} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f1f5f9' }}>
              CENTRAL FINITE DIFFERENCES: (f(x+&epsilon;) - f(x-&epsilon;)) / 2&epsilon;
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Step size (&epsilon;):</label>
            <select
              value={epsilon}
              onChange={(e) => {
                setEpsilon(e.target.value);
                if (onRevalidate) onRevalidate(e.target.value);
              }}
              style={{
                background: '#1b2336',
                border: '1px solid #2a354c',
                borderRadius: '4px',
                padding: '0.2rem 0.5rem',
                color: '#f1f5f9',
                fontSize: '0.8rem',
              }}
            >
              <option value="1e-4">1e-4</option>
              <option value="1e-5">1e-5</option>
              <option value="1e-6">1e-6 (Default)</option>
              <option value="1e-7">1e-7</option>
              <option value="1e-8">1e-8</option>
            </select>
          </div>
        </div>

        <button
          onClick={() => onRevalidate && onRevalidate(epsilon)}
          style={{
            background: '#1e293b',
            border: '1px solid #2a354c',
            color: '#38bdf8',
            padding: '0.35rem 0.75rem',
            borderRadius: '4px',
            fontSize: '0.78rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <RefreshCw size={13} />
          <span>Re-validate</span>
        </button>
      </div>

      <div className="table-container">
        {hasError && (
          <div style={{ padding: '1rem', color: '#f43f5e', background: 'rgba(244,63,94,0.1)', borderRadius: '4px', marginBottom: '1rem' }}>
            {finiteDifferences.error}
          </div>
        )}

        <table className="workbench-table">
          <thead>
            <tr>
              <th style={{ width: '120px' }}>Parameter</th>
              <th style={{ width: '180px' }}>Analytical (&part;f / &part;x)</th>
              <th style={{ width: '180px' }}>Numerical (Finite Diff)</th>
              <th style={{ width: '160px' }}>Absolute Error</th>
              <th style={{ width: '140px' }}>Relative Error</th>
              <th>Validation Status</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([param, data]) => {
              const isPass = data.status === 'PASS';
              return (
                <tr key={param}>
                  <td style={{ color: '#38bdf8', fontWeight: 700 }}>{param}</td>
                  <td style={{ color: '#f1f5f9', fontFamily: 'monospace' }}>
                    {data.analytical !== null ? Number(data.analytical).toFixed(8) : 'N/A'}
                  </td>
                  <td style={{ color: '#34d399', fontFamily: 'monospace' }}>
                    {data.numerical !== null ? Number(data.numerical).toFixed(8) : 'N/A'}
                  </td>
                  <td style={{ fontFamily: 'monospace', color: isPass ? '#94a3b8' : '#f59e0b' }}>
                    {data.absoluteError !== null ? String(data.absoluteError) : 'N/A'}
                  </td>
                  <td style={{ fontFamily: 'monospace', color: '#94a3b8' }}>
                    {data.relativeError !== null ? String(data.relativeError) : 'N/A'}
                  </td>
                  <td>
                    {isPass ? (
                      <span className="badge badge-emerald">
                        <CheckCircle2 size={12} style={{ marginRight: '3px' }} /> PASS (&lt;1e-4)
                      </span>
                    ) : (
                      <span className="badge badge-amber">
                        <AlertTriangle size={12} style={{ marginRight: '3px' }} /> {data.status}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
