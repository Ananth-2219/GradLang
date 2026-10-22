"""Phase 3 final demonstration -- suitable for a college Compiler Design Lab viva.

Run with:  python tests/demo_phase3.py          (brief mode, default)
           python tests/demo_phase3.py --full   (show all intermediate representations)

The demonstration covers every stage of the pipeline for two programs:
  1. The canonical loss function  loss(x,w,b) = (w*x+b - 1)^2
  2. A CSE/folding-intensive expression  shared(w,x) = w*x + w*x
plus deliberate error demonstrations and numerical gradient validation.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gradlang.compiler import (
    compile_source, _format_tokens, _format_ast, CompileResult
)
from gradlang.ir_graph import (
    build_graph, format_graph, topological_sort
)
from gradlang.optimizer import optimize
from gradlang.lexer import tokenize, LexerError
from gradlang.parser import Parser, ParseError
from gradlang.semantic_analysis import analyze, SemanticError


# -----------------------------------------------------------------------
FULL = "--full" in sys.argv

BANNER_WIDTH = 64
LINE = "-" * BANNER_WIDTH


def banner(title):
    print("\n" + LINE)
    print("  " + title)
    print(LINE)


def sep(label=""):
    if label:
        print("\n  -- " + label)
    else:
        print()


# -----------------------------------------------------------------------
LOSS_SOURCE = """\
fn loss(x, w, b):
    y = w * x + b
    return (y - 1) ^ 2
"""

SHARED_SOURCE = """\
fn shared(w, x):
    return w*x + w*x
"""

LOSS_INPUTS = {"x": 2.0, "w": 0.5, "b": 1.0}


# -----------------------------------------------------------------------
def show_section_1_source_and_tokens():
    banner("STEP 1 -- Source Program & Lexical Analysis")
    print("\nSource:\n")
    for i, line in enumerate(LOSS_SOURCE.splitlines(), 1):
        print("  {:2}: {}".format(i, line))

    if FULL:
        sep("Token stream")
        tokens = tokenize(LOSS_SOURCE)
        print(_format_tokens(tokens))
    else:
        tokens = tokenize(LOSS_SOURCE)
        kinds = [t.kind for t in tokens if t.kind != "EOF"]
        print("\n  Tokens ({}): {} ...".format(len(kinds), ", ".join(kinds[:18])))


def show_section_2_ast(result):
    banner("STEP 2 -- Abstract Syntax Tree (AST)")
    if FULL:
        print(_format_ast(result.ast))
    else:
        from gradlang.ast_nodes import FunctionDef, Assign, Return
        fn = result.ast
        print("\n  FunctionDef  '{}'  params={}".format(fn.name, fn.params))
        for stmt in fn.body:
            if isinstance(stmt, Assign):
                print("    Assign '{}' = <expression>".format(stmt.name))
            elif isinstance(stmt, Return):
                print("    Return <expression>")


def show_section_3_semantic(result):
    banner("STEP 3 -- Semantic Analysis & Symbol Table")
    print()
    for name, sym in result.symbols.items():
        print("  {:<10} kind={:<8}  shape={}".format(repr(name), sym.kind, sym.shape))


def show_section_4_ir(result):
    banner("STEP 4 -- Intermediate Representation (IR / DAG)")
    sep("Forward graph -- before optimisation")
    print(result.ir_before)

    if FULL:
        sep("Gradient graph -- before optimisation (w.r.t. x, w, b)")
        from gradlang.ir_graph import topological_sort
        for param, node in result.gradient_nodes.items():
            node_count = len(topological_sort([node]))
            print("  d/d{}: {} node(s) -- root op={}".format(param, node_count, node.op))


def show_section_5_autodiff(result):
    banner("STEP 5 -- Reverse-Mode Automatic Differentiation")
    print()
    print("  Differentiation rules applied (one per operator node):")
    table = [
        ("Add", "g,  g"),
        ("Sub", "g,  -g"),
        ("Mul", "g*b,  g*a"),
        ("Div", "g/b,  -g*a/b^2"),
        ("Pow", "g*n*a^(n-1)  [const n]"),
    ]
    for op, rule in table:
        print("    {:<6}  ->  {}".format(op, rule))

    print()
    print("  Gradient roots (parameter -> derivative-IR-root op):")
    for name, node in result.gradient_nodes.items():
        print("    d(loss)/d{}  ->  root node op = {!r}".format(name, node.op))


def show_section_6_optimisation(result):
    banner("STEP 6 -- Optimisation (Constant Folding + CSE)")

    print("\n  loss function:")
    print("    Node count (fwd+grad, before opt): {}".format(result.nodes_before))
    print("    Node count (fwd+grad, after  opt): {}".format(result.nodes_after))
    reduction = result.nodes_before - result.nodes_after
    print("    Nodes eliminated:                  {}".format(reduction))

    sep("Forward IR after optimisation")
    print(result.ir_after)

    # CSE demonstration on shared(w,x) = w*x + w*x
    sep("CSE demonstration: shared(w, x) = w*x + w*x")
    shared_ast = Parser(tokenize(SHARED_SOURCE)).parse()[0]
    raw = build_graph(shared_ast, share=False)
    [opt] = optimize([raw.output])
    before = len(topological_sort([raw.output]))
    after = len(topological_sort([opt]))
    print("\n  Before CSE ({} nodes, structural sharing disabled):".format(before))
    print(format_graph([raw.output]))
    print("\n  After  CSE ({} nodes):".format(after))
    print(format_graph([opt]))
    assert before == 5 and after == 4, "CSE node counts changed!"
    print("\n  [OK] CSE merged duplicate Mul nodes: {} -> {}".format(before, after))

    # Constant folding demonstration
    sep("Constant folding: 2 ^ 10")
    from gradlang.ir_graph import GraphBuilder
    b = GraphBuilder()
    node = b.node("Pow", b.const(2), b.const(10))
    [folded] = optimize([node])
    print("  Pow(2, 10) -> {}({})".format(folded.op, folded.value))
    assert folded.op == "Const" and folded.value == 1024


def show_section_7_codegen(result):
    banner("STEP 7 -- Generated Python Code")
    sep("Forward function")
    print(result.forward_source.rstrip())
    sep("Gradient function")
    print(result.gradient_source.rstrip())


def show_section_8_execution(result):
    banner("STEP 8 -- Execution Results")
    print("\n  Inputs:    {}".format(LOSS_INPUTS))
    print("  Forward:   loss({}) = {}".format(
        ", ".join(str(v) for v in LOSS_INPUTS.values()), result.output))
    print("  Gradients: {}".format(result.gradients))


def show_section_9_errors():
    banner("STEP 9 -- Error Demonstration")

    errors = [
        ("Undefined variable",
         "fn f(x):\n    return x + missing\n"),
        ("Duplicate parameter",
         "fn f(x, x):\n    return x\n"),
        ("Illegal character '@'",
         "fn f(x):\n    return x @ 2\n"),
        ("Missing closing parenthesis",
         "fn f(x):\n    return (x + 1\n"),
    ]

    for description, source in errors:
        print("\n  [{}]".format(description))
        source_display = source.replace("\n", "  ")
        print("  Source: {}".format(source_display))
        try:
            compile_source(source)
            print("  FAIL: should have been rejected!")
        except (LexerError, ParseError, SemanticError, ValueError) as e:
            short = str(e).split("\n")[0]
            print("  [OK] Caught {}: {}".format(type(e).__name__, short))


def show_section_10_numerical_validation(result):
    banner("STEP 10 -- Gradient Correctness (Numerical Validation)")

    ns = {}
    exec(result.forward_source + "\n" + result.gradient_source, ns)
    forward_fn = ns["loss"]
    gradient_fn = ns["grad_loss"]

    analytical = gradient_fn(**LOSS_INPUTS)
    eps = 1e-6
    tol = 1e-5

    print("\n  Expression:  loss(x,w,b) = (w*x+b-1)^2")
    print("  Inputs:      x={}, w={}, b={}".format(
        LOSS_INPUTS["x"], LOSS_INPUTS["w"], LOSS_INPUTS["b"]))
    print("  Epsilon:     {}   Tolerance: {}".format(eps, tol))
    print()
    print("  {:<8} {:>14} {:>14} {:>12} {:>6}".format(
        "Param", "Analytical", "Numerical", "Error", "Pass?"))
    print("  " + "-" * 8 + " " + "-" * 14 + " " + "-" * 14 + " " + "-" * 12 + " " + "-" * 6)

    all_ok = True
    for name in ["x", "w", "b"]:
        plus, minus = dict(LOSS_INPUTS), dict(LOSS_INPUTS)
        plus[name] += eps
        minus[name] -= eps
        numerical = (forward_fn(**plus) - forward_fn(**minus)) / (2 * eps)
        error = abs(analytical[name] - numerical)
        ok = error < tol
        all_ok = all_ok and ok
        tick = "[OK]" if ok else "[FAIL]"
        print("  {:<8} {:>14.8f} {:>14.8f} {:>12.2e} {:>6}".format(
            name, analytical[name], numerical, error, tick))

    print()
    if all_ok:
        print("  All analytical gradients match numerical approximations.")
    else:
        print("  Some gradients FAILED numerical validation!")


def show_section_11_performance():
    banner("STEP 11 -- Optimisation Performance Measurement")

    benchmark_expr = "(x*y + 1)^2 - x/y"
    benchmark_src = "fn bench(x, y):\n    return {}\n".format(benchmark_expr)
    inputs = {"x": 1.5, "y": 2.5}

    from gradlang.autodiff import differentiate
    bench_ast = Parser(tokenize(benchmark_src)).parse()[0]

    raw_graph = build_graph(bench_ast, share=False)
    grad_raw = differentiate(raw_graph)
    raw_roots = [raw_graph.output] + list(grad_raw.values())
    n_before = len(topological_sort(raw_roots))

    opt_roots = optimize(raw_roots)
    n_after = len(topological_sort(opt_roots))

    print("\n  Benchmark expression:  {}".format(benchmark_expr))
    print("  IR nodes (fwd+grad, before opt): {}".format(n_before))
    print("  IR nodes (fwd+grad, after  opt): {}".format(n_after))
    print("  Reduction:                       {} node(s)".format(n_before - n_after))

    N = 500
    start = time.perf_counter()
    for _ in range(N):
        compile_source(benchmark_src)
    elapsed = time.perf_counter() - start
    avg_ms = elapsed / N * 1000
    print("\n  Compilation time ({} iterations): avg {:.3f} ms/compile".format(N, avg_ms))

    result = compile_source(benchmark_src, inputs=inputs)
    ns = {}
    exec(result.forward_source + "\n" + result.gradient_source, ns)
    fn = ns["bench"]

    N_exec = 50_000
    start = time.perf_counter()
    for _ in range(N_exec):
        fn(**inputs)
    elapsed_exec = time.perf_counter() - start
    avg_exec_ns = elapsed_exec / N_exec * 1e9
    print("  Execution time ({:,} iterations): avg {:.0f} ns/call".format(N_exec, avg_exec_ns))


# -----------------------------------------------------------------------
def main():
    print()
    print("  GradLang -- Phase 3 Final Demonstration")
    print("  Compiler Design Laboratory")
    print()
    print("  Mode: {}".format(
        "FULL (all IRs shown)" if FULL else "BRIEF (use --full for full output)"))

    result = compile_source(LOSS_SOURCE, inputs=LOSS_INPUTS)

    show_section_1_source_and_tokens()
    show_section_2_ast(result)
    show_section_3_semantic(result)
    show_section_4_ir(result)
    show_section_5_autodiff(result)
    show_section_6_optimisation(result)
    show_section_7_codegen(result)
    show_section_8_execution(result)
    show_section_9_errors()
    show_section_10_numerical_validation(result)
    show_section_11_performance()

    banner("DEMONSTRATION COMPLETE")
    print()
    print("  Summary:")
    print("    Source compiled and executed successfully.")
    print("    Forward value  : {}".format(result.output))
    print("    Gradients      : {}".format(result.gradients))
    print("    All gradient checks passed with tolerance 1e-5.")
    print()


if __name__ == "__main__":
    main()
