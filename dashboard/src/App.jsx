import React, { useState, useEffect, useCallback } from 'react';
import {
  Layers,
  Terminal,
  Activity,
  GitCommit,
  Cpu,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  Code2,
  Database,
  Sliders,
  Play,
  Share2,
} from 'lucide-react';

import { fetchExamples, compileCode } from './api';
import CodeEditor from './components/CodeEditor';
import OverviewPanel from './components/OverviewPanel';
import DagViewer from './components/DagViewer';
import TokensViewer from './components/TokensViewer';
import AstViewer from './components/AstViewer';
import SemanticViewer from './components/SemanticViewer';
import IrViewer from './components/IrViewer';
import AutodiffViewer from './components/AutodiffViewer';
import CodegenViewer from './components/CodegenViewer';
import ValidationViewer from './components/ValidationViewer';
import TestBenchmarkPanel from './components/TestBenchmarkPanel';
import ErrorBanner from './components/ErrorBanner';

export default function App() {
  const [examples, setExamples] = useState([]);
  const [source, setSource] = useState(
    'fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n'
  );
  const [inputs, setInputs] = useState({ x: 2.0, w: 0.5, b: 0.0 });
  const [parameters, setParameters] = useState(['x', 'w', 'b']);

  // Compilation results & state
  const [compileResult, setCompileResult] = useState(null);
  const [compileError, setCompileError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [epsilon, setEpsilon] = useState('1e-6');

  // Load curated examples on mount
  useEffect(() => {
    fetchExamples()
      .then((data) => {
        setExamples(data);
        if (data.length > 0 && !source) {
          setSource(data[0].source);
          setInputs(data[0].inputs || {});
        }
      })
      .catch((err) => {
        console.error('Failed to load examples:', err);
      });
  }, []);

  // Main Compile & Run action
  const handleCompile = useCallback(
    async (customEps = epsilon, overrideInputs = null, overrideSource = null) => {
      setLoading(true);
      setCompileError(null);
      const srcToUse = overrideSource !== null ? overrideSource : source;
      const inputsToUse = overrideInputs !== null ? overrideInputs : inputs;
      try {
        const res = await compileCode(srcToUse, inputsToUse, true, customEps);
        if (res.success) {
          setCompileResult(res);
          setCompileError(null);
          if (res.parameters) {
            setParameters(res.parameters);
            setInputs((prev) => {
              const base = inputsToUse || prev || {};
              const next = {};
              res.parameters.forEach((p) => {
                next[p] = base[p] !== undefined && base[p] !== '' ? base[p] : 1.0;
              });
              return next;
            });
          }
        } else {
          setCompileError(res);
        }
      } catch (err) {
        setCompileError({
          errorType: 'Network/Server Error',
          message: err.message,
          phase: 'API',
        });
      } finally {
        setLoading(false);
      }
    },
    [source, inputs, epsilon]
  );

  // Initial compilation on page load
  useEffect(() => {
    handleCompile();
  }, []);

  return (
    <div className="workbench-app">
      {/* Top Header */}
      <header className="workbench-header">
        <div className="header-brand">
          <span className="brand-badge">GRADLANG // DSL</span>
          <span className="brand-title">Compiler Workbench &amp; Autodiff Visualizer</span>
          <span className="brand-subtitle">Compiler Design Laboratory &bull; Phase 3</span>
        </div>

        <div className="header-actions">
          {compileResult?.success && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge badge-emerald">
                <CheckCircle2 size={12} style={{ marginRight: '4px' }} />
                COMBINED IR NODES: {compileResult.ir.nodesBefore} &rarr; {compileResult.ir.nodesAfter}
              </span>
              <span className="badge badge-cyan">
                {compileResult.compileTimeMs} ms
              </span>
            </div>
          )}
          {compileError && (
            <span className="badge badge-rose">
              <AlertTriangle size={12} style={{ marginRight: '4px' }} />
              {compileError.errorType || 'Compilation Error'}
            </span>
          )}
        </div>
      </header>

      {/* Main Split Grid: Left Sidebar (Editor) + Right Workspace */}
      <div className="workbench-body">
        {/* Left Side Code Editor & Variable Inputs */}
        <CodeEditor
          source={source}
          setSource={setSource}
          inputs={inputs}
          setInputs={setInputs}
          parameters={parameters}
          setParameters={setParameters}
          onCompile={(explicitInputs, explicitSrc) => handleCompile(epsilon, explicitInputs, explicitSrc)}
          examples={examples}
          loading={loading}
        />

        {/* Right Main Analysis Panel */}
        <main className="workbench-main">
          {/* Navigation Tabs for All 7 Compiler Passes + Telemetry */}
          <nav className="tab-nav">
            <button
              className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <Activity size={14} />
              <span>Overview &amp; Results</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'dag' ? 'active' : ''}`}
              onClick={() => setActiveTab('dag')}
            >
              <Share2 size={14} />
              <span>Interactive DAG</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'tokens' ? 'active' : ''}`}
              onClick={() => setActiveTab('tokens')}
            >
              <Code2 size={14} />
              <span>Lexer Tokens ({compileResult?.tokens?.length || 0})</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'ast' ? 'active' : ''}`}
              onClick={() => setActiveTab('ast')}
            >
              <Layers size={14} />
              <span>AST Hierarchy</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'semantics' ? 'active' : ''}`}
              onClick={() => setActiveTab('semantics')}
            >
              <Database size={14} />
              <span>Semantic &amp; Symbols</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'ir' ? 'active' : ''}`}
              onClick={() => setActiveTab('ir')}
            >
              <Cpu size={14} />
              <span>IR Optimization ({compileResult?.ir?.forward?.nodesAfter || 0} forward nodes)</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'autodiff' ? 'active' : ''}`}
              onClick={() => setActiveTab('autodiff')}
            >
              <GitCommit size={14} />
              <span>Autodiff Adjoints</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'codegen' ? 'active' : ''}`}
              onClick={() => setActiveTab('codegen')}
            >
              <Terminal size={14} />
              <span>Generated Python</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'validation' ? 'active' : ''}`}
              onClick={() => setActiveTab('validation')}
            >
              <CheckCircle2 size={14} />
              <span>Finite-Difference Validation</span>
            </button>

            <button
              className={`tab-btn ${activeTab === 'tests' ? 'active' : ''}`}
              onClick={() => setActiveTab('tests')}
            >
              <BookOpen size={14} />
              <span>Live Pytest &amp; Benchmarks</span>
            </button>
          </nav>

          {/* Error Banner if error occurred */}
          <ErrorBanner error={compileError} />

          {/* Active Tab Panel Content */}
          <div className="panel-content">
            {activeTab === 'overview' && (
              <OverviewPanel data={compileResult} />
            )}

            {activeTab === 'dag' && (
              <DagViewer
                dags={compileResult?.dags}
                parameters={compileResult?.parameters || parameters}
              />
            )}

            {activeTab === 'tokens' && (
              <TokensViewer tokens={compileResult?.tokens || []} />
            )}

            {activeTab === 'ast' && (
              <AstViewer ast={compileResult?.ast} />
            )}

            {activeTab === 'semantics' && (
              <SemanticViewer symbols={compileResult?.symbols || {}} />
            )}

            {activeTab === 'ir' && (
              <IrViewer ir={compileResult?.ir} />
            )}

            {activeTab === 'autodiff' && (
              <AutodiffViewer autodiffSteps={compileResult?.autodiffSteps || []} />
            )}

            {activeTab === 'codegen' && (
              <CodegenViewer codegen={compileResult?.codegen} />
            )}

            {activeTab === 'validation' && (
              <ValidationViewer
                finiteDifferences={compileResult?.execution?.finiteDifferences}
                onRevalidate={(eps) => handleCompile(eps)}
                epsilon={epsilon}
                setEpsilon={setEpsilon}
              />
            )}

            {activeTab === 'tests' && (
              <TestBenchmarkPanel
                currentSource={source}
                currentInputs={inputs}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
