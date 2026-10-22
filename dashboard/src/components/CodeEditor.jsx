import React, { useEffect, useState } from 'react';
import { Play, Code2, Sliders, Sparkles } from 'lucide-react';

export default function CodeEditor({
  source,
  setSource,
  inputs,
  setInputs,
  parameters,
  onCompile,
  examples = [],
  loading = false,
}) {
  const [selectedExampleId, setSelectedExampleId] = useState('');

  // When an example is chosen, update source and default inputs
  const handleSelectExample = (e) => {
    const id = e.target.value;
    setSelectedExampleId(id);
    const ex = examples.find((item) => item.id === id);
    if (ex) {
      setSource(ex.source);
      if (ex.inputs) {
        setInputs(ex.inputs);
      }
    }
  };

  const handleInputChange = (param, val) => {
    setInputs((prev) => ({
      ...prev,
      [param]: val === '' ? '' : parseFloat(val),
    }));
  };

  // Keyboard shortcut Ctrl+Enter / Cmd+Enter to compile
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        onCompile();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCompile]);

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
          onChange={(e) => setSource(e.target.value)}
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
            {parameters.length > 0 ? `${parameters.length} parameter(s)` : 'Awaiting compilation'}
          </span>
        </div>

        {parameters.length > 0 ? (
          <div className="params-grid">
            {parameters.map((param) => (
              <div key={param} className="param-field">
                <label>{param} =</label>
                <input
                  type="number"
                  step="any"
                  className="param-input"
                  value={inputs[param] !== undefined ? inputs[param] : ''}
                  onChange={(e) => handleInputChange(param, e.target.value)}
                  placeholder="0.0"
                />
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic' }}>
            Parameters detected automatically after compilation.
          </div>
        )}
      </div>

      {/* Compile Action Button */}
      <div className="compile-bar">
        <button
          className="btn-compile"
          onClick={onCompile}
          disabled={loading}
        >
          <Play size={15} fill="#fff" />
          <span>{loading ? 'Compiling...' : 'Compile & Run Pipeline'}</span>
        </button>
      </div>
    </aside>
  );
}
