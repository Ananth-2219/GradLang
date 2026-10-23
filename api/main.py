"""FastAPI backend connecting GradLang compiler to the visualization dashboard.

Provides endpoints for:
  - Compilation & execution with deep serialization (tokens, AST, symbols, IR, DAGs, codegen)
  - Reverse-mode autodiff step-by-step trace
  - Finite-difference gradient validation
  - Interactive compiler example catalog
  - Live test suite execution (real pytest metrics)
  - Detailed compiler phase micro-benchmarking
"""

import time
import math
import re
import pytest
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# GradLang compiler imports
from gradlang.compiler import compile_source, CompileResult
from gradlang.lexer import tokenize, Token, LexerError
from gradlang.parser import Parser, ParseError
from gradlang.ast_nodes import (
    FunctionDef, Assign, Return, BinOp, UnaryOp, Var, Num, Call
)
from gradlang.symbol_table import Symbol, SemanticError
from gradlang.semantic_analysis import analyze
from gradlang.ir_graph import (
    Node, Graph, topological_sort, format_graph, build_graph
)
from gradlang.autodiff import differentiate, RULES
from gradlang.optimizer import optimize
from gradlang.codegen import generate_code, load_functions
from .dag_education import describe_node, evaluate_nodes, explain_gradients

app = FastAPI(
    title="GradLang Compiler Workbench API",
    description="Real-time interactive compiler pipeline inspection and reverse-mode autodiff workbench",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class CompileRequest(BaseModel):
    source: str
    inputs: Optional[Dict[str, Any]] = None
    validate_gradients: bool = True
    epsilon: float = 1e-6


class TestRunResponse(BaseModel):
    total: int
    passed: int
    failed: int
    duration_seconds: float
    output: str
    tests: List[Dict[str, Any]]


class BenchmarkRequest(BaseModel):
    source: str
    inputs: Optional[Dict[str, float]] = None
    iterations: int = Field(default=50, ge=5, le=500)


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------

def optimization_metrics(nodes_before: int, nodes_after: int) -> Dict[str, Any]:
    """Compare node counts within one graph scope, counting shared nodes once."""
    reduction = nodes_before - nodes_after
    return {
        "nodesBefore": nodes_before,
        "nodesAfter": nodes_after,
        "nodeReduction": reduction,
        "percentReduction": round(reduction / nodes_before * 100, 1) if nodes_before else 0.0,
    }


def serialize_token(tok: Token) -> Dict[str, Any]:
    return {
        "kind": tok.kind,
        "value": tok.value,
        "line": tok.line,
        "column": tok.column,
    }


def serialize_ast(node: Any) -> Dict[str, Any]:
    """Serialize an AST node to a JSON-compatible tree structure."""
    if isinstance(node, FunctionDef):
        return {
            "type": "FunctionDef",
            "name": node.name,
            "params": node.params,
            "line": getattr(node, "line", 0),
            "body": [serialize_ast(stmt) for stmt in node.body],
        }
    elif isinstance(node, Assign):
        return {
            "type": "Assign",
            "name": node.name,
            "line": getattr(node, "line", 0),
            "value": serialize_ast(node.value),
        }
    elif isinstance(node, Return):
        return {
            "type": "Return",
            "line": getattr(node, "line", 0),
            "value": serialize_ast(node.value),
        }
    elif isinstance(node, BinOp):
        return {
            "type": "BinOp",
            "operator": node.operator,
            "line": getattr(node, "line", 0),
            "left": serialize_ast(node.left),
            "right": serialize_ast(node.right),
        }
    elif isinstance(node, UnaryOp):
        return {
            "type": "UnaryOp",
            "operator": node.operator,
            "line": getattr(node, "line", 0),
            "operand": serialize_ast(node.operand),
        }
    elif isinstance(node, Num):
        return {
            "type": "Num",
            "value": node.value,
            "line": getattr(node, "line", 0),
        }
    elif isinstance(node, Var):
        return {
            "type": "Var",
            "name": node.name,
            "line": getattr(node, "line", 0),
        }
    elif isinstance(node, Call):
        return {
            "type": "Call",
            "name": node.name,
            "line": getattr(node, "line", 0),
            "arguments": [serialize_ast(arg) for arg in node.arguments],
        }
    return {"type": "Unknown", "repr": repr(node)}


def serialize_dag(
    roots: List[Node],
    root_labels: Optional[Dict[Node, Any]] = None,
    inputs: Optional[Dict[str, float]] = None,
    evaluated_values: Optional[Dict[Node, float]] = None,
) -> Dict[str, Any]:
    """Convert a set of DAG roots into a directed graph for visualization."""
    nodes = topological_sort(roots)
    values = evaluate_nodes(roots, inputs, evaluated_values) if inputs is not None else None
    node_to_id = {node: f"node_{i}" for i, node in enumerate(nodes)}
    
    # Calculate consumer counts (out-degree in data-flow)
    consumer_counts: Dict[Node, int] = {node: 0 for node in nodes}
    consumers_map: Dict[Node, List[str]] = {node: [] for node in nodes}
    for node in nodes:
        for inp in node.inputs:
            if inp in consumer_counts:
                consumer_counts[inp] += 1
                consumers_map[inp].append(node_to_id[node])

    graph_nodes = []
    for i, node in enumerate(nodes):
        node_id = node_to_id[node]
        is_root = root_labels is not None and node in root_labels
        root_name = root_labels[node] if is_root else None
        root_names = root_name if isinstance(root_name, list) else ([root_name] if is_root else [])
        
        # Display label
        if node.op == "Var":
            label = f"Var({node.value})"
            kind = "var"
        elif node.op == "Const":
            label = f"Const({node.value})"
            kind = "const"
        elif node.op == "Log":
            label = "Log"
            kind = "op"
        else:
            label = node.op
            kind = "op"

        graph_nodes.append({
            "id": node_id,
            "op": node.op,
            "value": node.value,
            "label": label,
            "kind": kind,
            "inputs": [node_to_id[inp] for inp in node.inputs],
            "consumers": consumers_map[node],
            "consumerCount": consumer_counts[node],
            "isShared": consumer_counts[node] > 1,
            "isRoot": is_root,
            "rootName": ", ".join(root_names) if root_names else None,
            "rootNames": root_names,
            "sharedExplanation": (
                f"This value has {consumer_counts[node]} input uses in this graph, "
                "possibly repeated inputs of the same operation. It is computed once and reused "
                "instead of duplicating its computation. This is reuse, not proof of an eliminated node."
                if consumer_counts[node] > 1 else "This value has at most one input use in this graph."
            ),
            **(describe_node(node, values) if values is not None else {
                "evaluatedValue": None, "inputValues": [], "calculation": None,
                "explanation": "Supply numerical inputs to evaluate this node.",
            }),
        })

    edges = []
    edge_set = set()
    for node in nodes:
        target_id = node_to_id[node]
        for arg_idx, inp in enumerate(node.inputs):
            source_id = node_to_id[inp]
            edge_key = (source_id, target_id, arg_idx)
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append({
                    "id": f"e_{source_id}_{target_id}_{arg_idx}",
                    "source": source_id,
                    "target": target_id,
                    "argIndex": arg_idx,
                })

    return {
        "nodes": graph_nodes,
        "edges": edges,
        "nodeCount": len(nodes),
        "sharedCount": sum(1 for n in nodes if consumer_counts[n] > 1),
    }


def trace_autodiff(graph: Graph) -> List[Dict[str, Any]]:
    """Simulate reverse-mode autodiff and capture each adjoint step."""
    order = topological_sort([graph.output])
    node_to_name = {node: f"n{i}" for i, node in enumerate(order)}
    for node in order:
        if node.op == "Var":
            node_to_name[node] = f"Var({node.value})"
        elif node.op == "Const":
            node_to_name[node] = f"Const({node.value})"

    steps = []
    # In reverse topological order
    for node in reversed(order):
        step = {
            "nodeId": f"n{order.index(node)}",
            "op": node.op,
            "value": node.value,
            "name": node_to_name[node],
            "inputs": [node_to_name[child] for child in node.inputs],
            "ruleApplied": None,
            "explanation": "",
        }
        if node == graph.output:
            step["ruleApplied"] = "Seed"
            step["explanation"] = "Seed upstream adjoint dy/dy = 1"
        elif node.op in ("Var", "Const"):
            step["ruleApplied"] = "Leaf"
            step["explanation"] = f"Leaf accumulator for {node.op} '{node.value}'"
        elif node.op in RULES:
            rule_names = {
                "Add": "d(u+v) = (du, dv)",
                "Sub": "d(u-v) = (du, -dv)",
                "Mul": "d(u*v) = (v*du, u*dv) [Product Rule]",
                "Div": "d(u/v) = (du/v, -u*du/v^2) [Quotient Rule]",
                "Pow": "d(u^c) = c*u^(c-1)*du [Power Rule] / d(a^v) = a^v*ln(a)*dv",
            }
            step["ruleApplied"] = f"{node.op} Rule"
            step["explanation"] = rule_names.get(node.op, f"Chain rule for {node.op}")
        else:
            step["ruleApplied"] = "General"
            step["explanation"] = f"Propagation through {node.op}"
        steps.append(step)
    return steps


def compute_finite_differences(
    forward_fn,
    inputs: Dict[str, float],
    analytical_grads: Dict[str, float],
    epsilon: float = 1e-6
) -> Dict[str, Any]:
    """Compute central finite differences and compare against analytical gradients."""
    results = {}
    for param, analytical in analytical_grads.items():
        if param not in inputs:
            continue
        plus = dict(inputs)
        minus = dict(inputs)
        plus[param] += epsilon
        minus[param] -= epsilon

        try:
            f_plus = forward_fn(**plus)
            f_minus = forward_fn(**minus)
            numerical = (f_plus - f_minus) / (2.0 * epsilon)
            abs_err = abs(analytical - numerical)
            denom = max(abs(analytical), abs(numerical), 1e-8)
            rel_err = abs_err / denom
            passed = abs_err < 1e-4 or rel_err < 1e-4

            results[param] = {
                "analytical": analytical,
                "numerical": round(numerical, 8),
                "absoluteError": float(f"{abs_err:.2e}"),
                "relativeError": float(f"{rel_err:.2e}"),
                "status": "PASS" if passed else "WARN",
            }
        except Exception as e:
            results[param] = {
                "analytical": analytical,
                "numerical": None,
                "absoluteError": None,
                "relativeError": None,
                "status": f"ERROR: {str(e)}",
            }
    return results


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "GradLang Compiler API"}


@app.get("/api/examples")
def get_examples():
    """Curated suite of DSL programs demonstrating compiler features."""
    return [
        {
            "id": "loss_linear",
            "name": "Linear Regression Loss",
            "category": "Machine Learning",
            "description": "Canonical squared loss (y - 1)^2 for a linear model y = w * x + b. Computes analytical gradients for w and b.",
            "source": "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n",
            "inputs": {"x": 2.0, "w": 0.5, "b": 0.0},
        },
        {
            "id": "cse_demo",
            "name": "Common Subexpression Elimination (CSE)",
            "category": "Optimization",
            "description": "Demonstrates structural DAG sharing. x * y is computed once and shared in both forward and backward passes.",
            "source": "fn f(x, y):\n    return x * y + x * y\n",
            "inputs": {"x": 3.0, "y": 4.0},
        },
        {
            "id": "polynomial",
            "name": "Cubic Polynomial (Power Rule)",
            "category": "Calculus",
            "description": "Tests power rule differentiation for integer powers x^3 and x^2, with constant factor scaling.",
            "source": "fn poly(x):\n    return 3 * x ^ 3 - 5 * x ^ 2 + 2 * x + 7\n",
            "inputs": {"x": 2.0},
        },
        {
            "id": "quotient",
            "name": "Quotient Rule (Rational Function)",
            "category": "Calculus",
            "description": "Division operation triggering reverse-mode quotient rule: d(u/v) = du/v - u*dv/v^2.",
            "source": "fn ratio(u, v):\n    return (u + 1) / (v - 2)\n",
            "inputs": {"u": 3.0, "v": 4.0},
        },
        {
            "id": "rosenbrock",
            "name": "Rosenbrock Valley Function",
            "category": "Optimization",
            "description": "Classic non-convex benchmark function with curved valley: (1-x)^2 + 100*(y - x^2)^2.",
            "source": "fn rosenbrock(x, y):\n    return (1 - x) ^ 2 + 100 * (y - x ^ 2) ^ 2\n",
            "inputs": {"x": 1.0, "y": 1.0},
        },
        {
            "id": "constant_fold",
            "name": "Constant Folding & Arithmetic",
            "category": "Optimization",
            "description": "Demonstrates compile-time constant arithmetic evaluation and simplification.",
            "source": "fn fold(x):\n    return x * (2 + 3) + (10 / 2) * x\n",
            "inputs": {"x": 2.5},
        },
        {
            "id": "multi_variable",
            "name": "Three-Variable Chain Rule",
            "category": "Calculus",
            "description": "Multi-variable intermediate assignment with shared variable reuse.",
            "source": "fn compose(a, b, c):\n    t = a * b\n    return t * c + t\n",
            "inputs": {"a": 2.0, "b": 3.0, "c": 4.0},
        },
    ]


@app.post("/api/compile")
def compile_code(req: CompileRequest):
    """Compile GradLang source text, execute with inputs, and return full telemetry."""
    source = req.source.strip()
    if not source:
        raise HTTPException(status_code=400, detail={"errorType": "EmptySource", "message": "Source code cannot be empty"})

    t0 = time.perf_counter()

    # Pre-parse inputs if provided (convert numeric strings, filter invalid)
    prepared_inputs: Optional[Dict[str, float]] = None
    if req.inputs is not None:
        clean = {}
        for k, v in req.inputs.items():
            if v is not None and v != "":
                try:
                    clean[str(k)] = float(v)
                except (ValueError, TypeError):
                    pass
        prepared_inputs = clean

    try:
        # Reconcile inputs with declared function parameters
        preview_tokens = tokenize(source)
        preview_funcs = Parser(preview_tokens).parse()
        if preview_funcs:
            func_params = list(preview_funcs[0].params)
            if prepared_inputs is not None:
                # Keep only declared parameters
                prepared_inputs = {k: v for k, v in prepared_inputs.items() if k in func_params}
                # For any parameter not yet supplied, default to 1.0 so execution evaluates
                for p in func_params:
                    if p not in prepared_inputs:
                        prepared_inputs[p] = 1.0
            else:
                # When inputs was omitted, evaluate with default 1.0 so gradients are available
                prepared_inputs = {p: 1.0 for p in func_params}

        result = compile_source(source, inputs=prepared_inputs)
    except LexerError as exc:
        msg = str(exc)
        line, col = _extract_line_col(msg)
        return {
            "success": False,
            "phase": "Lexer",
            "errorType": "LexerError",
            "message": msg,
            "line": line,
            "column": col,
        }
    except ParseError as exc:
        msg = str(exc)
        line, col = _extract_line_col(msg)
        return {
            "success": False,
            "phase": "Parser",
            "errorType": "ParseError",
            "message": msg,
            "line": line,
            "column": col,
        }
    except SemanticError as exc:
        msg = str(exc)
        line, col = _extract_line_col(msg)
        return {
            "success": False,
            "phase": "SemanticAnalysis",
            "errorType": "SemanticError",
            "message": msg,
            "line": line,
            "column": col,
        }
    except ZeroDivisionError as exc:
        return {
            "success": False,
            "phase": "Execution",
            "errorType": "ZeroDivisionError",
            "message": f"Mathematical division by zero during execution: {exc}",
            "line": None,
            "column": None,
        }
    except ValueError as exc:
        msg = str(exc)
        line, col = _extract_line_col(msg)
        return {
            "success": False,
            "phase": "Compilation/Execution",
            "errorType": "ValueError",
            "message": msg,
            "line": line,
            "column": col,
        }
    except Exception as exc:
        return {
            "success": False,
            "phase": "General",
            "errorType": type(exc).__name__,
            "message": str(exc),
            "line": None,
            "column": None,
        }
    total_time_ms = (time.perf_counter() - t0) * 1000.0

    # Serialization
    serialized_tokens = [serialize_token(t) for t in result.tokens]
    serialized_ast = serialize_ast(result.ast)
    serialized_symbols = {
        name: {"kind": sym.kind, "shape": list(sym.shape)}
        for name, sym in result.symbols.items()
    }

    # Build DAG representations
    evaluated_values = evaluate_nodes(
        [result.graph.output, result.output_opt, *result.gradient_nodes_opt.values()],
        prepared_inputs,
    )
    gradient_guides = explain_gradients(result.graph, prepared_inputs)
    # 1. Forward raw DAG
    fwd_raw_dag = serialize_dag(
        [result.graph.output],
        root_labels={result.graph.output: f"{result.graph.name} (output)"},
        inputs=prepared_inputs, evaluated_values=evaluated_values,
    )

    # 2. Forward optimized DAG
    fwd_opt_dag = serialize_dag(
        [result.output_opt],
        root_labels={result.output_opt: f"{result.graph.name} (opt)"},
        inputs=prepared_inputs, evaluated_values=evaluated_values,
    )

    # 3. Combined forward + gradients (shows shared nodes across both passes!)
    combined_roots = [result.output_opt] + [
        result.gradient_nodes_opt[p] for p in result.parameters
    ]
    combined_labels = {result.output_opt: ["Forward Output"]}
    for p in result.parameters:
        combined_labels.setdefault(result.gradient_nodes_opt[p], []).append(f"d/d{p}")
    combined_dag = serialize_dag(combined_roots, root_labels=combined_labels,
                                 inputs=prepared_inputs, evaluated_values=evaluated_values)

    # 4. Individual derivative DAGs (optimized)
    derivatives_opt_dag = {}
    symbolic_gradients = {}
    gradient_node_counts = {}
    for param in result.parameters:
        if param in result.gradient_nodes_opt:
            root_node = result.gradient_nodes_opt[param]
            derivatives_opt_dag[param] = serialize_dag(
                [root_node],
                root_labels={root_node: f"d/d{param}"},
                inputs=prepared_inputs, evaluated_values=evaluated_values,
            )
            derivatives_opt_dag[param]["gradientExplanation"] = gradient_guides[param]
            symbolic_gradients[param] = format_graph([root_node])
            gradient_node_counts[param] = len(topological_sort([root_node]))

    # Autodiff steps trace
    autodiff_steps = trace_autodiff(result.graph)

    # Finite difference validation
    finite_diff_results = None
    if req.validate_gradients and prepared_inputs and result.gradients is not None:
        try:
            forward_fn, _ = load_functions(
                result.graph.name,
                result.forward_source,
                result.gradient_source
            )
            finite_diff_results = compute_finite_differences(
                forward_fn,
                prepared_inputs,
                result.gradients,
                epsilon=req.epsilon
            )
        except Exception as e:
            finite_diff_results = {"error": f"Validation failed: {str(e)}"}

    # Keep legacy combined metrics while exposing explicit like-for-like scopes.
    forward_metrics = optimization_metrics(
        result.forward_nodes_before, result.forward_nodes_after
    )
    combined_metrics = optimization_metrics(
        result.combined_nodes_before, result.combined_nodes_after
    )

    return {
        "success": True,
        "parameters": result.parameters,
        "output": result.output,
        "gradients": result.gradients,
        "symbolicGradients": symbolic_gradients,
        "gradientNodeCounts": gradient_node_counts,
        "tokens": serialized_tokens,
        "ast": serialized_ast,
        "symbols": serialized_symbols,
        "ir": {
            "before": result.ir_before,
            "after": result.ir_after,
            **combined_metrics,  # Backward compatibility: these have always been combined.
            "forward": forward_metrics,  # Counts for the forward-only before/after listings.
            "combined": combined_metrics,  # Union of forward + all derivative graphs.
        },
        "dags": {
            "forwardRaw": fwd_raw_dag,
            "forwardOpt": fwd_opt_dag,
            "combined": combined_dag,
            "derivatives": derivatives_opt_dag,
        },
        "autodiffSteps": autodiff_steps,
        "codegen": {
            "forwardSource": result.forward_source,
            "gradientSource": result.gradient_source,
        },
        "execution": {
            "output": result.output,
            "gradients": result.gradients,
            "inputs": prepared_inputs,
            "finiteDifferences": finite_diff_results,
        },
        "compileTimeMs": round(total_time_ms, 3),
    }


@app.post("/api/test", response_model=TestRunResponse)
def run_tests():
    """Execute the real test suite and return live passed/failed statistics."""
    import subprocess
    import sys

    t0 = time.perf_counter()
    # Run pytest directly with python -m pytest
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--no-header"],
        capture_output=True,
        text=True,
        cwd="c:\\GradLang"
    )
    duration = time.perf_counter() - t0

    output = proc.stdout + proc.stderr
    
    # Parse output to extract test names and results
    tests = []
    passed = 0
    failed = 0
    for line in output.splitlines():
        if "::" in line and ("PASSED" in line or "FAILED" in line):
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                status = parts[1]
                if "PASSED" in status:
                    passed += 1
                elif "FAILED" in status:
                    failed += 1
                tests.append({"name": name, "status": status})

    # Regex search for total passed/failed summary line
    summary_match = re.search(r"(\d+)\s+passed", output)
    if summary_match and passed == 0:
        passed = int(summary_match.group(1))

    fail_match = re.search(r"(\d+)\s+failed", output)
    if fail_match:
        failed = int(fail_match.group(1))

    total = passed + failed

    return TestRunResponse(
        total=total,
        passed=passed,
        failed=failed,
        duration_seconds=round(duration, 3),
        output=output,
        tests=tests,
    )


@app.post("/api/benchmark")
def run_benchmark(req: BenchmarkRequest):
    """Benchmark each individual phase of the compiler over N iterations."""
    source = req.source.strip()
    iterations = req.iterations

    try:
        # 1. Lexing
        t_lex = []
        for _ in range(iterations):
            s = time.perf_counter()
            tokens = tokenize(source)
            t_lex.append((time.perf_counter() - s) * 1e6)

        # 2. Parsing
        t_parse = []
        for _ in range(iterations):
            s = time.perf_counter()
            ast_node = Parser(tokens).parse()[0]
            t_parse.append((time.perf_counter() - s) * 1e6)

        # 3. Semantic Analysis
        t_sem = []
        for _ in range(iterations):
            s = time.perf_counter()
            symbols = analyze(ast_node)
            t_sem.append((time.perf_counter() - s) * 1e6)

        # 4. IR Graph Building
        t_ir = []
        for _ in range(iterations):
            s = time.perf_counter()
            graph = build_graph(ast_node)
            t_ir.append((time.perf_counter() - s) * 1e6)

        # 5. Reverse-Mode Autodiff
        t_diff = []
        for _ in range(iterations):
            s = time.perf_counter()
            grad_nodes = differentiate(graph)
            t_diff.append((time.perf_counter() - s) * 1e6)

        # 6. Optimization (Constant Folding & CSE)
        all_roots = [graph.output] + [grad_nodes[k] for k in graph.parameters]
        t_opt = []
        for _ in range(iterations):
            s = time.perf_counter()
            opt_roots = optimize(all_roots)
            t_opt.append((time.perf_counter() - s) * 1e6)

        # 7. Code Generation
        output_opt = opt_roots[0]
        grad_opt = {k: opt_roots[i + 1] for i, k in enumerate(graph.parameters)}
        t_codegen = []
        for _ in range(iterations):
            s = time.perf_counter()
            fwd_src, grad_src = generate_code(
                graph.name, list(graph.parameters), output_opt, grad_opt
            )
            t_codegen.append((time.perf_counter() - s) * 1e6)

        # 8. Execution (if inputs provided)
        t_exec = []
        if req.inputs:
            fwd_fn, grad_fn = load_functions(graph.name, fwd_src, grad_src)
            for _ in range(iterations):
                s = time.perf_counter()
                fwd_fn(**req.inputs)
                grad_fn(**req.inputs)
                t_exec.append((time.perf_counter() - s) * 1e6)

        def summarize(times):
            if not times:
                return None
            return {
                "mean_us": round(sum(times) / len(times), 2),
                "min_us": round(min(times), 2),
                "max_us": round(max(times), 2),
            }

        total_mean_us = (
            summarize(t_lex)["mean_us"] +
            summarize(t_parse)["mean_us"] +
            summarize(t_sem)["mean_us"] +
            summarize(t_ir)["mean_us"] +
            summarize(t_diff)["mean_us"] +
            summarize(t_opt)["mean_us"] +
            summarize(t_codegen)["mean_us"]
        )

        return {
            "iterations": iterations,
            "total_compile_mean_us": round(total_mean_us, 2),
            "phases": {
                "lexer": summarize(t_lex),
                "parser": summarize(t_parse),
                "semantic": summarize(t_sem),
                "ir_graph": summarize(t_ir),
                "autodiff": summarize(t_diff),
                "optimizer": summarize(t_opt),
                "codegen": summarize(t_codegen),
                "execution": summarize(t_exec) if t_exec else None,
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Diagnostics Helpers
# ---------------------------------------------------------------------------

def _extract_line_col(msg: str):
    """Extract line and column numbers from GradLang error messages."""
    line = None
    col = None
    m_line = re.search(r"line\s+(\d+)", msg, re.IGNORECASE)
    if m_line:
        try:
            line = int(m_line.group(1))
        except ValueError:
            pass
    m_col = re.search(r"column\s+(\d+)", msg, re.IGNORECASE)
    if m_col:
        try:
            col = int(m_col.group(1))
        except ValueError:
            pass
    return line, col
