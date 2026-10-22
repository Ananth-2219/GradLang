import React, { useState } from 'react';
import { Copy, Check, Terminal, FileCode } from 'lucide-react';

export default function CodegenViewer({ codegen }) {
  const [copiedForward, setCopiedForward] = useState(false);
  const [copiedGrad, setCopiedGrad] = useState(false);

  if (!codegen) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        No generated code available.
      </div>
    );
  }

  const copyToClipboard = (text, setCopied) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="diff-grid">
        {/* Forward Python Code */}
        <div className="diff-col">
          <div className="diff-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={14} style={{ color: '#10b981' }} />
              <span>FORWARD EVALUATION (Python AST)</span>
            </div>
            <button
              onClick={() => copyToClipboard(codegen.forwardSource, setCopiedForward)}
              style={{
                background: 'transparent',
                border: '1px solid #2a354c',
                color: '#cbd5e1',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.75rem',
              }}
            >
              {copiedForward ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
              {copiedForward ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div className="diff-body" style={{ color: '#34d399' }}>
            {codegen.forwardSource || '# No forward code generated'}
          </div>
        </div>

        {/* Gradient Python Code */}
        <div className="diff-col">
          <div className="diff-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FileCode size={14} style={{ color: '#f59e0b' }} />
              <span>ANALYTICAL GRADIENT FUNCTION (Python AST)</span>
            </div>
            <button
              onClick={() => copyToClipboard(codegen.gradientSource, setCopiedGrad)}
              style={{
                background: 'transparent',
                border: '1px solid #2a354c',
                color: '#cbd5e1',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.75rem',
              }}
            >
              {copiedGrad ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
              {copiedGrad ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div className="diff-body" style={{ color: '#fbbf24' }}>
            {codegen.gradientSource || '# No gradient code generated'}
          </div>
        </div>
      </div>
    </div>
  );
}
