import React, { useState } from 'react';
import { Search } from 'lucide-react';

export default function TokensViewer({ tokens = [] }) {
  const [filter, setFilter] = useState('');

  const filteredTokens = tokens.filter((t) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      t.kind.toLowerCase().includes(q) ||
      String(t.value).toLowerCase().includes(q) ||
      `${t.line}:${t.column}`.includes(q)
    );
  });

  const getKindBadgeClass = (kind) => {
    switch (kind) {
      case 'FN':
      case 'RETURN':
        return 'badge-purple';
      case 'IDENT':
        return 'badge-cyan';
      case 'NUMBER':
        return 'badge-emerald';
      case 'SYMBOL':
      case 'ASSIGN':
        return 'badge-amber';
      case 'EOF':
        return 'badge-rose';
      default:
        return 'badge-cyan';
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Table Filter Bar */}
      <div
        style={{
          padding: '0.6rem 1.25rem',
          background: '#0f1420',
          borderBottom: '1px solid #2a354c',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '280px' }}>
          <Search size={14} style={{ color: '#64748b' }} />
          <input
            type="text"
            placeholder="Filter tokens by kind or value..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{
              background: '#1b2336',
              border: '1px solid #2a354c',
              borderRadius: '4px',
              padding: '0.3rem 0.6rem',
              color: '#f1f5f9',
              fontSize: '0.8rem',
              outline: 'none',
              width: '100%',
            }}
          />
        </div>
        <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
          Total Tokens: {tokens.length}
        </span>
      </div>

      <div className="table-container">
        <table className="workbench-table">
          <thead>
            <tr>
              <th style={{ width: '60px' }}>#</th>
              <th style={{ width: '100px' }}>Line : Col</th>
              <th style={{ width: '140px' }}>Token Kind</th>
              <th>Lexeme / Value</th>
            </tr>
          </thead>
          <tbody>
            {filteredTokens.map((t, idx) => (
              <tr key={idx}>
                <td style={{ color: '#64748b' }}>{idx + 1}</td>
                <td style={{ color: '#38bdf8' }}>{t.line}:{t.column}</td>
                <td>
                  <span className={`badge ${getKindBadgeClass(t.kind)}`}>
                    {t.kind}
                  </span>
                </td>
                <td style={{ color: '#f1f5f9', fontWeight: 500 }}>
                  {t.value ? `"${t.value}"` : <span style={{ color: '#64748b', fontStyle: 'italic' }}>&empty;</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
