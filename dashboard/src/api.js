/**
 * Client API for communicating with the GradLang FastAPI backend.
 */

const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function fetchExamples() {
  const res = await fetch(`${API_BASE}/examples`);
  if (!res.ok) throw new Error('Failed to load examples');
  return res.json();
}

export async function compileCode(source, inputs = null, validateGradients = true, epsilon = 1e-6, signal = null) {
  const res = await fetch(`${API_BASE}/compile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      source,
      inputs,
      validate_gradients: validateGradients,
      epsilon: parseFloat(epsilon) || 1e-6,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail?.message || errorData.message || 'Compilation request failed');
  }
  return res.json();
}

export async function runTests() {
  const res = await fetch(`${API_BASE}/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Test execution failed');
  return res.json();
}

export async function runBenchmark(source, inputs = null, iterations = 50) {
  const res = await fetch(`${API_BASE}/benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source,
      inputs,
      iterations: parseInt(iterations, 10) || 50,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Benchmark execution failed');
  }
  return res.json();
}
