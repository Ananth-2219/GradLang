import React, { useEffect, useState } from 'react';
import { Play, Code2, Sliders, Sparkles } from 'lucide-react';

function extractParams(src) {
  if (!src) return [];
  const match = src.match(/fn\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)/);
  if (!match) return [];
  return match[1]
    .split(',')
    .map((s) => s.trim())
    .filter((s) => Boolean(s) && /^[A-Za-z_][A-Za-z0-9_]*$/.test(s));
}

export default function CodeEditor({
  source,
  setSource,
  inputs,
  setInputs,
  parameters,
  setParameters,
  onCompile,
  examples = [],
  loading = false,
}) {
  const [selectedExampleId, setSelectedExampleId] = useState('');

  // When an example is chosen, update source, parameters, and default inputs
  const handleSelectExample = (e) => {
    const id = e.target.value;
    setSelectedExampleId(id);
    const ex = examples.find((item) => item.id === id);
    if (ex) {
      setSource(ex.source);
      const parsedParams = extractParams(ex.source);
      if (parsedParams.length > 0 && setParameters) {
        setParameters(parsedParams);
      }
      if (ex.inputs) {
        setInputs(ex.inputs);
        if (onCompile) {
          onCompile(ex.inputs, ex.source);
        }
      }
    }
  };

  const handleSourceChange = (newSrc) => {
    setSource(newSrc);
    const parsedParams = extractParams(newSrc);
    if (parsedParams.length > 0) {
      if (setParameters) setParameters(parsedParams);
      setInputs((prev) => {
        const next = {};
        parsedParams.forEach((p) => {
          next[p] = prev[p] !== undefined && prev[p] !== '' ? prev[p] : 1.0;
        });
        return next;
      });
    }
  };

  const handleInputChange = (param, val) => {
    setInputs((prev) => ({
      ...prev,
      [param]: val === '' ? '' : (isNaN(parseFloat(val)) ? 0 : parseFloat(val)),
    }));
  };

  const handleCompileClick = () => {
    const activeParams = parameters && parameters.length > 0 ? parameters : extractParams(source);
    const resolvedInputs = {};
    activeParams.forEach((p) => {
      const raw = inputs[p];
      if (raw !== undefined && raw !== '' && !isNaN(Number(raw))) {
        resolvedInputs[p] = Number(raw);
      } else {
        resolvedInputs[p] = 1.0;
      }
    });
    if (onCompile) {
      onCompile(resolvedInputs, source);
    }
  };

  // Keyboard shortcut Ctrl+Enter / Cmd+Enter to compile
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleCompileClick();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCompile, inputs, source, parameters]);

  const activeParams = parameters && parameters.length > 0 ? parameters : extractParams(source);

  return (
    <aside className="workbench-sidebar">
      {/* Example Selection Toolbar */}
      <div className="editor-toolbar">
        <div className="toolbar-row">
          <span className="toolbar-label">
            <Sparkles size={12} style={{ marginRight: '4px', verticalAlign: 'middle', color: '#38bdf8' }} />
            Example Programs
          </span>
          <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Ctrl + Enter</span>
        </div>
        <select
          className="example-select"
          value={selectedExampleId}
          onChange={handleSelectExample}
        >
          <option value="">-- Choose DSL Example --</option>
          {examples.map((ex) => (
            <option key={ex.id} value={ex.id}>
              [{ex.category}] {ex.name}
            </option>
          ))}
        </select>
      </div>

      {/* Code Textarea with line numbers */}
      <div className="editor-wrapper">
        <div
          style={{
            padding: '0.5rem 1rem',
            background: '#090c12',
            borderBottom: '1px solid #1e2638',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Code2 size={14} style={{ color: '#38bdf8' }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>GRADLANG SOURCE (.grad)</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Indentation = 4 spaces</span>
        </div>

        <textarea
          className="code-textarea"
          value={source}
          onChange={(e) => handleSourceChange(e.target.value)}
          placeholder="fn f(x):&#10;    return x ^ 2"
          spellCheck="false"
        />
      </div>

      {/* Variable Inputs Section */}
      <div className="params-section">
        <div className="params-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sliders size={13} style={{ color: '#f59e0b' }} />
            <span>FUNCTION INPUTS</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
            {activeParams.length > 0 ? `${activeParams.length} parameter(s)` : 'Awaiting parameters'}
          </span>
        </div>

        {activeParams.length > 0 ? (
          <div className="params-grid">
            {activeParams.map((param) => (
              <div key={param} className="param-field">
                <label>{param} =</label>
                <input
                  type="number"
                  step="any"
                  className="param-input"
                  value={inputs[param] !== undefined ? inputs[param] : ''}
                  onChange={(e) => handleInputChange(param, e.target.value)}
                  placeholder="1.0"
                />
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic' }}>
            Parameters detected automatically from function header.
          </div>
        )}
      </div>

      {/* Compile Action Button */}
      <div className="compile-bar">
        <button
          className="btn-compile"
          onClick={handleCompileClick}
          disabled={loading}
        >
          <Play size={15} fill="#fff" />
          <span>{loading ? 'Compiling...' : 'Compile & Run Pipeline'}</span>
        </button>
      </div>
    </aside>
  );
}
