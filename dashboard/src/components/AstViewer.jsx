import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Folder, FileCode, Tag } from 'lucide-react';

function AstTreeNode({ node, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!node) return null;

  const nodeType = node.type || 'Node';
  const hasChildren =
    (node.body && node.body.length > 0) ||
    node.left ||
    node.right ||
    node.operand ||
    node.value?.type ||
    (node.arguments && node.arguments.length > 0);

  const getBadgeColor = (type) => {
    switch (type) {
      case 'FunctionDef':
        return '#818cf8';
      case 'Assign':
        return '#38bdf8';
      case 'Return':
        return '#f59e0b';
      case 'BinOp':
        return '#60a5fa';
      case 'UnaryOp':
        return '#c084fc';
      case 'Num':
        return '#34d399';
      case 'Var':
        return '#38bdf8';
      case 'Call':
        return '#ec4899';
      default:
        return '#94a3b8';
    }
  };

  return (
    <div style={{ marginLeft: '1.25rem', borderLeft: '1px solid #1e2638', paddingLeft: '0.5rem' }}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '0.25rem 0.5rem',
          borderRadius: '4px',
          cursor: hasChildren ? 'pointer' : 'default',
          userSelect: 'none',
          background: isOpen && hasChildren ? 'rgba(56, 189, 248, 0.05)' : 'transparent',
        }}
      >
        {hasChildren ? (
          isOpen ? <ChevronDown size={14} color="#64748b" /> : <ChevronRight size={14} color="#64748b" />
        ) : (
          <span style={{ width: '14px', display: 'inline-block' }}>&bull;</span>
        )}

        <span
          style={{
            fontSize: '0.75rem',
            fontFamily: 'monospace',
            fontWeight: 700,
            color: getBadgeColor(nodeType),
            background: 'rgba(255,255,255,0.06)',
            padding: '1px 6px',
            borderRadius: '3px',
          }}
        >
          {nodeType}
        </span>

        {/* Extra Node Attributes Preview */}
        {node.name && (
          <span style={{ fontSize: '0.8rem', color: '#f1f5f9', fontWeight: 600 }}>
            "{node.name}"
          </span>
        )}
        {node.params && (
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
            params=[{node.params.join(', ')}]
          </span>
        )}
        {node.operator && (
          <span style={{ fontSize: '0.8rem', color: '#f59e0b', fontWeight: 700 }}>
            op: '{node.operator}'
          </span>
        )}
        {node.value !== undefined && typeof node.value !== 'object' && (
          <span style={{ fontSize: '0.8rem', color: '#34d399', fontWeight: 600 }}>
            = {String(node.value)}
          </span>
        )}
        {node.line > 0 && (
          <span style={{ fontSize: '0.7rem', color: '#64748b', marginLeft: 'auto' }}>
            line {node.line}
          </span>
        )}
      </div>

      {isOpen && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '2px' }}>
          {node.body && node.body.map((child, i) => (
            <AstTreeNode key={i} node={child} defaultOpen={true} />
          ))}
          {node.value && typeof node.value === 'object' && (
            <AstTreeNode node={node.value} defaultOpen={true} />
          )}
          {node.left && <AstTreeNode node={node.left} defaultOpen={true} />}
          {node.right && <AstTreeNode node={node.right} defaultOpen={true} />}
          {node.operand && <AstTreeNode node={node.operand} defaultOpen={true} />}
          {node.arguments && node.arguments.map((arg, i) => (
            <AstTreeNode key={i} node={arg} defaultOpen={true} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AstViewer({ ast }) {
  if (!ast) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No Abstract Syntax Tree data available.
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8' }}>
          AST STRUCTURE (Program Hierarchy)
        </span>
        <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
          Click nodes to expand / collapse
        </span>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '1.25rem' }}>
        <AstTreeNode node={ast} defaultOpen={true} />
      </div>
    </div>
  );
}
