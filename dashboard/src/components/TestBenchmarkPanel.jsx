import React, { useState } from 'react';
import { Play, CheckCircle2, XCircle, Gauge, Activity, RefreshCw } from 'lucide-react';
import { runTests, runBenchmark } from '../api';

export default function TestBenchmarkPanel({ currentSource, currentInputs }) {
  // Test Suite State
  const [testResult, setTestResult] = useState(null);
  const [testingLoading, setTestingLoading] = useState(false);
  const [testError, setTestError] = useState(null);

  // Benchmark State
  const [benchResult, setBenchResult] = useState(null);
  const [benchLoading, setBenchLoading] = useState(false);
  const [benchError, setBenchError] = useState(null);
  const [iterations, setIterations] = useState(50);

  const handleRunTests = async () => {
    setTestingLoading(true);
    setTestError(null);
    try {
      const res = await runTests();
      setTestResult(res);
    } catch (err) {
      setTestError(err.message);
    } finally {
      setTestingLoading(false);
    }
  };

  const handleRunBenchmark = async () => {
    if (!currentSource) return;
    setBenchLoading(true);
    setBenchError(null);
    try {
      const res = await runBenchmark(currentSource, currentInputs, iterations);
      setBenchResult(res);
    } catch (err) {
      setBenchError(err.message);
    } finally {
      setBenchLoading(false);
    }
  };

  const phases = benchResult?.phases || {};

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'auto', padding: '1.5rem', gap: '1.5rem' }}>
      {/* 1. Live Pytest Test Suite Runner */}
      <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} style={{ color: '#10b981' }} />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9' }}>
                Live Pytest Execution Suite
              </h3>
            </div>
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '2px' }}>
              Executes the real test suite in Python and reports live measurements.
            </p>
          </div>

          <button
            onClick={handleRunTests}
            disabled={testingLoading}
            style={{
              background: 'linear-gradient(135deg, #059669, #10b981)',
              color: '#fff',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              fontWeight: 600,
              fontSize: '0.82rem',
              cursor: testingLoading ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            {testingLoading ? <RefreshCw size={14} className="spin" /> : <Play size={14} fill="#fff" />}
            <span>{testingLoading ? 'Running Pytest...' : 'Run Test Suite'}</span>
          </button>
        </div>

        {testError && (
          <div style={{ padding: '0.75rem', background: 'rgba(244,63,94,0.15)', border: '1px solid #f43f5e', borderRadius: '4px', color: '#fecdd3', fontSize: '0.8rem', marginBottom: '1rem' }}>
            {testError}
          </div>
        )}

        {testResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Summary Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem' }}>
              <div style={{ background: '#161c2c', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>TOTAL TESTS</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: '#f1f5f9' }}>{testResult.total}</div>
              </div>
              <div style={{ background: '#161c2c', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>PASSED</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: '#10b981' }}>{testResult.passed}</div>
              </div>
              <div style={{ background: '#161c2c', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>FAILED</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: testResult.failed > 0 ? '#f43f5e' : '#64748b' }}>
                  {testResult.failed}
                </div>
              </div>
              <div style={{ background: '#161c2c', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>REAL DURATION</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'monospace', color: '#38bdf8' }}>{testResult.duration_seconds}s</div>
              </div>
            </div>

            {/* Test List Explorer */}
            {testResult.tests && testResult.tests.length > 0 && (
              <div style={{ maxHeight: '200px', overflowY: 'auto', background: '#090c12', border: '1px solid #1e2638', borderRadius: '6px', padding: '0.5rem' }}>
                {testResult.tests.slice(0, 50).map((t, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderBottom: '1px solid #161c2c' }}>
                    <span style={{ color: '#cbd5e1', fontFamily: 'monospace' }}>{t.name}</span>
                    <span className={`badge ${t.status.includes('PASSED') ? 'badge-emerald' : 'badge-rose'}`}>
                      {t.status}
                    </span>
                  </div>
                ))}
                {testResult.tests.length > 50 && (
                  <div style={{ textAlign: 'center', fontSize: '0.72rem', color: '#64748b', padding: '0.4rem' }}>
                    ... and {testResult.tests.length - 50} more tests verified
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. Live Compiler Micro-Benchmarking */}
      <div style={{ background: '#0f1420', border: '1px solid #2a354c', borderRadius: '8px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Gauge size={18} style={{ color: '#38bdf8' }} />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9' }}>
                Phase-by-Phase Compiler Micro-Benchmarking
              </h3>
            </div>
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '2px' }}>
              Measures wall-clock time (&mu;s) for each individual compilation stage across N runs.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Iterations:</label>
            <input
              type="number"
              min="5"
              max="200"
              value={iterations}
              onChange={(e) => setIterations(e.target.value)}
              style={{
                background: '#1b2336',
                border: '1px solid #2a354c',
                borderRadius: '4px',
                padding: '0.3rem 0.5rem',
                color: '#fff',
                fontSize: '0.8rem',
                width: '65px',
              }}
            />
            <button
              onClick={handleRunBenchmark}
              disabled={benchLoading}
              style={{
                background: 'linear-gradient(135deg, #0284c7, #2563eb)',
                color: '#fff',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: '4px',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: benchLoading ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {benchLoading ? <RefreshCw size={14} className="spin" /> : <Activity size={14} />}
              <span>{benchLoading ? 'Benchmarking...' : 'Run Benchmark'}</span>
            </button>
          </div>
        </div>

        {benchError && (
          <div style={{ padding: '0.75rem', background: 'rgba(244,63,94,0.15)', border: '1px solid #f43f5e', borderRadius: '4px', color: '#fecdd3', fontSize: '0.8rem', marginBottom: '1rem' }}>
            {benchError}
          </div>
        )}

        {benchResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ background: '#161c2c', padding: '0.75rem 1rem', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.82rem', color: '#cbd5e1' }}>
                Mean Full Compile Time ({benchResult.iterations} iterations):
              </span>
              <span style={{ fontSize: '1.2rem', fontFamily: 'monospace', fontWeight: 700, color: '#38bdf8' }}>
                {benchResult.total_compile_mean_us} &mu;s
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {[
                { name: 'Lexical Analysis (Tokens)', key: 'lexer' },
                { name: 'Parser (AST Construction)', key: 'parser' },
                { name: 'Semantic Analysis & Symbol Table', key: 'semantic' },
                { name: 'IR DAG Construction', key: 'ir_graph' },
                { name: 'Reverse-Mode Automatic Differentiation', key: 'autodiff' },
                { name: 'Optimizer (Folding & CSE)', key: 'optimizer' },
                { name: 'Code Generation (Python AST)', key: 'codegen' },
                { name: 'Execution (Forward & Gradients)', key: 'execution' },
              ].map(({ name, key }) => {
                const stats = phases[key];
                if (!stats) return null;
                const pct = Math.min(100, Math.max(5, (stats.mean_us / benchResult.total_compile_mean_us) * 100));
                return (
                  <div key={key} style={{ background: '#161c2c', padding: '0.75rem 1rem', borderRadius: '6px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                      <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{name}</span>
                      <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: '#94a3b8' }}>
                        <span style={{ color: '#38bdf8', fontWeight: 700 }}>{stats.mean_us} &mu;s</span> (min: {stats.min_us}&mu;s, max: {stats.max_us}&mu;s)
                      </div>
                    </div>
                    <div className="bench-bar-container">
                      <div className="bench-bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
