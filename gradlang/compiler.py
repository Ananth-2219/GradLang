"""Unified compiler pipeline: source text to executed result in one call.

This module is the single user-facing entry point introduced in Phase 3.
It wires together all existing passes without altering them and returns
a structured CompileResult that exposes every intermediate representation
for inspection, testing, and demonstration.

Pipeline
--------
source text
  -> tokenize          (lexer.py)
  -> parse             (parser.py)
  -> analyze           (semantic_analysis.py  /  symbol_table.py)
  -> build_graph       (ir_graph.py)
  -> differentiate     (autodiff.py)
  -> optimize          (optimizer.py)
  -> generate_code     (codegen.py)
  -> load_functions    (codegen.py)
  -> execute with inputs
  -> return CompileResult
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .lexer import tokenize, Token, LexerError
from .parser import Parser, ParseError
from .ast_nodes import FunctionDef
from .semantic_analysis import analyze
from .symbol_table import SemanticError, Symbol
from .ir_graph import build_graph, format_graph, topological_sort, Graph
from .autodiff import differentiate
from .optimizer import optimize
from .codegen import generate_code, load_functions


# ---------------------------------------------------------------------------
# Public result container
# ---------------------------------------------------------------------------

@dataclass
class CompileResult:
    """Holds every artifact produced by the compiler pipeline.

    All fields are populated even when execution is skipped (inputs=None).
    The *output* and *gradients* fields are None when inputs are not provided.
    """
    # Source & tokens
    source: str
    tokens: List[Token]

    # AST
    ast: FunctionDef

    # Symbol table  {name: Symbol}
    symbols: Dict[str, Symbol]

    # IR graph (before optimisation)
    graph: Graph
    ir_before: str          # human-readable topological listing

    # Gradients dict {param_name: derivative_root_node}
    gradient_nodes: Dict[str, Any]

    # Optimised roots
    output_opt: Any         # optimised forward output node
    gradient_nodes_opt: Dict[str, Any]
    ir_after: str           # human-readable listing after optimisation

    # Combined forward + gradient statistics (legacy public fields)
    nodes_before: int
    nodes_after: int

    # Generated Python source
    forward_source: str
    gradient_source: str

    # Execution results (None when inputs were not provided)
    output: Optional[float]
    gradients: Optional[Dict[str, float]]

    # Parameter list in declaration order
    parameters: List[str]

    @property
    def forward_nodes_before(self) -> int:
        """Reachable forward nodes, matching ir_before."""
        return len(topological_sort([self.graph.output]))

    @property
    def forward_nodes_after(self) -> int:
        """Reachable optimized forward nodes, matching ir_after."""
        return len(topological_sort([self.output_opt]))

    @property
    def combined_nodes_before(self) -> int:
        """Unique nodes across the forward and all raw derivative roots."""
        return self.nodes_before

    @property
    def combined_nodes_after(self) -> int:
        """Unique nodes across the forward and all optimized derivative roots."""
        return self.nodes_after


# ---------------------------------------------------------------------------
# Core pipeline function
# ---------------------------------------------------------------------------

def compile_source(
    source: str,
    inputs: Optional[Dict[str, float]] = None,
    parameter_types: Optional[Dict[str, Symbol]] = None,
) -> CompileResult:
    """Compile a GradLang program and optionally execute it.

    Parameters
    ----------
    source:
        Complete GradLang source text (may contain multiple functions; only
        the first function is compiled through the full pipeline).
    inputs:
        Mapping of parameter name to numerical value.  When provided the
        generated forward function and gradient function are called and their
        results stored in CompileResult.output and CompileResult.gradients.
        When None, code is generated and loaded but not executed.
    parameter_types:
        Optional explicit Symbol annotations forwarded to the semantic pass.

    Returns
    -------
    CompileResult populated with every compiler artefact.

    Raises
    ------
    LexerError, ParseError
        On lexical or syntactic errors in *source*.
    SemanticError
        On undefined variables, duplicate parameters, etc.
    ValueError
        On IR/codegen errors such as reserved Python keyword names.
    ZeroDivisionError, ValueError
        On mathematical errors during execution.
    """
    # ---- Lexical analysis --------------------------------------------------
    tokens = tokenize(source)

    # ---- Parsing -----------------------------------------------------------
    functions = Parser(tokens).parse()
    ast_node = functions[0]

    # ---- Semantic analysis -------------------------------------------------
    symbols = analyze(ast_node, parameter_types)

    # ---- IR construction ---------------------------------------------------
    graph = build_graph(ast_node, parameter_types)
    parameters = list(graph.parameters)

    # Collect forward + all gradient roots so CSE can cross them
    gradient_nodes_raw = differentiate(graph)

    # Count the union of reachable forward + gradient nodes, sharing included once.
    raw_roots_for_count = [graph.output] + list(gradient_nodes_raw.values())
    nodes_before = len(topological_sort(raw_roots_for_count))

    ir_before = format_graph([graph.output])

    # ---- Optimisation ------------------------------------------------------
    all_roots = [graph.output] + [gradient_nodes_raw[k] for k in parameters]
    optimised = optimize(all_roots)
    output_opt = optimised[0]
    gradient_nodes_opt = {k: optimised[i + 1] for i, k in enumerate(parameters)}

    nodes_after = len(topological_sort([output_opt] + list(gradient_nodes_opt.values())))
    ir_after = format_graph([output_opt])

    # ---- Code generation ---------------------------------------------------
    forward_src, gradient_src = generate_code(
        graph.name, parameters, output_opt, gradient_nodes_opt
    )

    # ---- Load generated functions ------------------------------------------
    forward_fn, gradient_fn = load_functions(graph.name, forward_src, gradient_src)

    # ---- Execute (if inputs provided) --------------------------------------
    result_output: Optional[float] = None
    result_gradients: Optional[Dict[str, float]] = None

    if inputs is not None:
        _validate_inputs(inputs, parameters)
        result_output = forward_fn(**inputs)
        result_gradients = gradient_fn(**inputs)

    return CompileResult(
        source=source,
        tokens=tokens,
        ast=ast_node,
        symbols=symbols,
        graph=graph,
        ir_before=ir_before,
        gradient_nodes=gradient_nodes_raw,
        output_opt=output_opt,
        gradient_nodes_opt=gradient_nodes_opt,
        ir_after=ir_after,
        nodes_before=nodes_before,
        nodes_after=nodes_after,
        forward_source=forward_src,
        gradient_source=gradient_src,
        output=result_output,
        gradients=result_gradients,
        parameters=parameters,
    )


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _validate_inputs(inputs: Dict[str, float], parameters: List[str]) -> None:
    """Raise ValueError with a clear message for bad inputs."""
    missing = [p for p in parameters if p not in inputs]
    if missing:
        raise ValueError(
            f"Missing input values for parameters: {missing}. "
            f"Expected keys: {parameters}"
        )
    extra = [k for k in inputs if k not in parameters]
    if extra:
        raise ValueError(
            f"Unexpected input keys: {extra}. "
            f"Known parameters: {parameters}"
        )
    for name, value in inputs.items():
        if not isinstance(value, (int, float)):
            raise TypeError(
                f"Input {name!r} must be a number; got {type(value).__name__!r}"
            )


def _format_tokens(tokens) -> str:
    """Return a compact token table for display."""
    lines = ["  {:<8} {:<15} {}".format("Line:Col", "Kind", "Value")]
    lines.append("  " + "-" * 40)
    for tok in tokens:
        if tok.kind == "EOF":
            break
        val = repr(tok.value) if tok.value else "(empty)"
        lines.append("  {}:{:<6} {:<15} {}".format(
            tok.line, tok.column, tok.kind, val))
    return "\n".join(lines)


def _format_ast(node, indent: int = 0) -> str:
    """Compact multi-line representation of an AST node."""
    prefix = "  " * indent
    from .ast_nodes import (FunctionDef, Assign, Return,
                             BinOp, UnaryOp, Var, Num, Call)
    if isinstance(node, FunctionDef):
        header = f"{prefix}FunctionDef '{node.name}' params={node.params}"
        children = "\n".join(_format_ast(s, indent + 1) for s in node.body)
        return header + "\n" + children
    if isinstance(node, Assign):
        return (f"{prefix}Assign '{node.name}' =\n"
                + _format_ast(node.value, indent + 1))
    if isinstance(node, Return):
        return f"{prefix}Return\n" + _format_ast(node.value, indent + 1)
    if isinstance(node, BinOp):
        return (f"{prefix}BinOp '{node.operator}'\n"
                + _format_ast(node.left, indent + 1) + "\n"
                + _format_ast(node.right, indent + 1))
    if isinstance(node, UnaryOp):
        return (f"{prefix}UnaryOp '{node.operator}'\n"
                + _format_ast(node.operand, indent + 1))
    if isinstance(node, Num):
        return f"{prefix}Num({node.value})"
    if isinstance(node, Var):
        return f"{prefix}Var('{node.name}')"
    if isinstance(node, Call):
        args = ", ".join(_format_ast(a, 0) for a in node.arguments)
        return f"{prefix}Call '{node.name}'({args})"
    return f"{prefix}{repr(node)}"


def main_cli(argv=None):
    """Lightweight command-line interface for GradLang.

    Usage
    -----
    python -m gradlang.compiler <source_file> [key=value ...]
    python -m gradlang.compiler --expr "fn f(x): return x^2" x=3

    Options
    -------
    --verbose   Print tokens, AST, IR, and generated code.
    --no-exec   Compile only; do not execute.
    --help      Show this message.
    """
    import sys
    import os

    if argv is None:
        argv = sys.argv[1:]

    if not argv or "--help" in argv or "-h" in argv:
        print(main_cli.__doc__)
        return 0

    verbose = "--verbose" in argv
    no_exec = "--no-exec" in argv
    argv = [a for a in argv if a not in ("--verbose", "--no-exec")]

    # Determine source
    source: Optional[str] = None
    inputs: Dict[str, float] = {}
    remaining = []

    if argv and argv[0] == "--expr":
        if len(argv) < 2:
            print("Error: --expr requires a source string argument.", file=sys.stderr)
            return 2
        source = argv[1]
        remaining = argv[2:]
    elif argv:
        path = argv[0]
        remaining = argv[1:]
        if not os.path.isfile(path):
            print(f"Error: file not found: {path!r}", file=sys.stderr)
            return 2
        with open(path, encoding="utf-8-sig") as fh:
            source = fh.read()

    # Parse key=value pairs
    for arg in remaining:
        if "=" not in arg:
            print(f"Error: expected key=value, got {arg!r}", file=sys.stderr)
            return 2
        key, _, raw = arg.partition("=")
        try:
            inputs[key.strip()] = float(raw.strip())
        except ValueError:
            print(f"Error: value for {key!r} is not a number: {raw!r}", file=sys.stderr)
            return 2

    if source is None:
        print("Error: no source file or --expr provided.", file=sys.stderr)
        return 2

    # Compile
    try:
        result = compile_source(
            source,
            inputs=inputs if (inputs and not no_exec) else None,
        )
    except (LexerError, ParseError) as exc:
        print(f"\nSyntax error: {exc}", file=sys.stderr)
        return 1
    except SemanticError as exc:
        print(f"\nSemantic error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, ZeroDivisionError) as exc:
        print(f"\nCompilation/execution error: {exc}", file=sys.stderr)
        return 1

    # Print results
    sep = "=" * 60

    if verbose:
        print(sep)
        print("SOURCE")
        print(sep)
        print(result.source.rstrip())

        print(f"\n{sep}")
        print("TOKENS")
        print(sep)
        print(_format_tokens(result.tokens))

        print(f"\n{sep}")
        print("ABSTRACT SYNTAX TREE")
        print(sep)
        print(_format_ast(result.ast))

        print(f"\n{sep}")
        print("SYMBOL TABLE")
        print(sep)
        for name, sym in result.symbols.items():
            print(f"  {name!r:15} kind={sym.kind}  shape={sym.shape}")

        print(f"\n{sep}")
        print("INTERMEDIATE REPRESENTATION (forward, before optimisation)")
        print(sep)
        print(result.ir_before)

        print(f"\n{sep}")
        print("INTERMEDIATE REPRESENTATION (forward, after optimisation)")
        print(sep)
        print(result.ir_after)
        print(f"  Forward nodes: {result.forward_nodes_before} -> {result.forward_nodes_after}")
        print(f"  Combined forward + gradient nodes: {result.nodes_before} -> {result.nodes_after}")

        print(f"\n{sep}")
        print("GENERATED PYTHON CODE")
        print(sep)
        print(result.forward_source.rstrip())
        print()
        print(result.gradient_source.rstrip())

    if result.output is not None:
        print(f"\n{sep}")
        print("EXECUTION RESULT")
        print(sep)
        print(f"  forward({', '.join(f'{k}={v}' for k,v in inputs.items())}) = {result.output}")
        print(f"  gradients = {result.gradients}")

    elif no_exec:
        print("Compilation successful (execution skipped).")
    else:
        print("Compilation successful.")
        if result.parameters:
            print(f"  Parameters: {result.parameters}")
            print("  Provide key=value arguments to execute.")

    return 0
