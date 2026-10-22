# GradLang — Phases 1, 2, and 3

GradLang is a Compiler Design Laboratory project implementing a domain-specific language (DSL) for mathematical expressions.  The compiler performs lexical analysis, recursive-descent parsing, semantic analysis, IR construction, **reverse-mode automatic differentiation**, IR optimisation, and Python code generation.  Phase 3 adds a unified pipeline, a comprehensive test suite, a CLI entry point, and a final demonstration.

---

## Repository layout

```text
GradLang/
├── gradlang/
│   ├── __init__.py          Package docstring
│   ├── __main__.py          CLI entry point (python -m gradlang ...)
│   ├── lexer.py             Tokeniser + layout rules
│   ├── parser.py            Recursive-descent parser
│   ├── ast_nodes.py         Eight AST dataclasses
│   ├── symbol_table.py      Symbol table, shape inference, SemanticError
│   ├── semantic_analysis.py Public semantic pass (analyze)
│   ├── ir_graph.py          Identity-based DAG + GraphBuilder
│   ├── autodiff.py          Reverse-mode differentiation pass
│   ├── optimizer.py         Constant folding + structural CSE
│   ├── codegen.py           Python code emission + load_functions
│   └── compiler.py          [Phase 3] Unified pipeline + CompileResult + CLI
├── tests/
│   ├── demo_phase1.py       Phase 1 demo (parse + error)
│   ├── test_phase1.py       Phase 1 unit tests (7 tests)
│   ├── demo_phase2.py       Phase 2 demo (full pass + CSE + finite diff)
│   ├── test_phase2.py       Phase 2 unit tests (6 tests)
│   ├── demo_phase3.py       [Phase 3] Final review demo (11 steps)
│   └── test_phase3.py       [Phase 3] Comprehensive tests (88 tests)
└── README.md
```

Python 3.8 or newer.  No third-party dependencies.

---

## Quick start

```sh
# Run all tests (101 tests total)
python -m unittest discover -s tests -v

# Run only the new Phase 3 tests
python -m unittest tests/test_phase3.py -v

# Run the Phase 3 final demonstration
python tests/demo_phase3.py           # brief
python tests/demo_phase3.py --full    # show all IRs

# Run the Phase 2 demo (unchanged from earlier phases)
python tests/demo_phase2.py

# CLI: compile and execute a .gl source file
python -m gradlang my_program.gl x=2.0 w=0.5 b=1.0

# CLI: verbose mode (tokens, AST, IR, generated code)
python -m gradlang my_program.gl --verbose x=2.0 w=0.5 b=1.0

# CLI: compile only, skip execution
python -m gradlang my_program.gl --no-exec
```

---

## Compiler pipeline

```
Source text
  |
  v  tokenize()           lexer.py
Tokens
  |
  v  Parser.parse()       parser.py
AST (FunctionDef, ...)
  |
  v  analyze()            semantic_analysis.py / symbol_table.py
Symbol table  {name: Symbol}
  |
  v  build_graph()        ir_graph.py
Forward computation DAG (Node objects)
  |
  v  differentiate()      autodiff.py
Gradient DAG  {param: Node}
  |
  v  optimize()           optimizer.py
Optimised forward + gradient DAGs
  |
  v  generate_code()      codegen.py
Python source strings (forward function + gradient function)
  |
  v  load_functions()     codegen.py
Callable Python functions
  |
  v  fn(**inputs)
Result + gradient dict
```

The Phase 3 entry point `compile_source(source, inputs)` runs the full pipeline and returns a `CompileResult` dataclass containing every artefact.

---

## Supported language syntax

```
fn loss(x, w, b):
    y = w * x + b
    return (y - 1) ^ 2
```

### EBNF grammar

```ebnf
program        = function, { function }, EOF ;
function       = "fn", IDENT, "(", [ parameters ], ")", ":", NEWLINE,
                 INDENT, { assignment }, return_stmt, DEDENT ;
parameters     = IDENT, { ",", IDENT } ;
assignment     = IDENT, "=", expression, NEWLINE ;
return_stmt    = "return", expression, NEWLINE ;

expression     = additive ;
additive       = multiplicative, { ("+" | "-"), multiplicative } ;
multiplicative = unary, { ("*" | "/"), unary } ;
unary          = "-", unary | power ;
power          = primary, [ "^", unary ] ;
primary        = NUMBER
               | IDENT, [ "(", [ arguments ], ")" ]
               | "(", expression, ")" ;
arguments      = expression, { ",", expression } ;
```

### Operator precedence (lowest to highest)

| Level | Operators | Associativity |
|-------|-----------|---------------|
| 1     | `+`, `-`  | Left          |
| 2     | `*`, `/`  | Left          |
| 3     | unary `-` | Right         |
| 4     | `^`       | Right         |

### Layout rules

- Spaces only; tabs are rejected.
- Blank lines are skipped.
- Body lines must have one consistent positive indentation level.
- `INDENT`/`DEDENT` tokens are generated automatically.

### Numeric literals

`12`, `1.25`, `.5`, `2e-3` are all valid.  A trailing decimal point (`1.`) is not supported.  Integer-valued literals produce `int`; any literal with `.` or `e/E` produces `float`.

### Limitations

- Function calls are parsed but rejected at the semantic pass — their derivative rules are not yet implemented.
- Vector parameters can be annotated externally (`Symbol("vector", (3,))`) and pass semantic checks, but IR lowering and execution are scalar-only.
- No control flow, comments, string literals, or multi-line expressions.

---

## Module descriptions

### `lexer.py`
`tokenize(source)` scans one line at a time, normalises line endings, rejects tabs, tracks indentation with a stack, and emits layout tokens (`INDENT`, `DEDENT`, `NEWLINE`, `EOF`) alongside numbers, identifiers, keywords, and single-character punctuation.

### `parser.py`
`Parser(tokens).parse()` implements the EBNF grammar with one method per production.  Left-associativity is built by loops; right-associativity by recursion.  One-token lookahead distinguishes variables from calls.

### `ast_nodes.py`
Eight frozen dataclasses: `FunctionDef`, `Assign`, `Return`, `BinOp`, `UnaryOp`, `Num`, `Var`, `Call`.  The `line` field is metadata excluded from structural equality.

### `symbol_table.py`
`build_symbol_table(function, parameter_types)` performs a single ordered walk: each assignment's RHS is checked before the target is inserted, so use-before-definition is caught correctly.  Shape inference applies scalar broadcast rules.

### `semantic_analysis.py`
`analyze(function, parameter_types)` is the public entry point; it delegates directly to `build_symbol_table`.

### `ir_graph.py`
Frozen `Node(op, inputs, value)` objects form an identity-based DAG.  `GraphBuilder` optionally interns nodes by structural key (construction-time CSE).  `build_graph` lowers an AST to a `Graph(name, parameters, output)`.  Unary minus is lowered as `Sub(Const(0), operand)`.

### `autodiff.py`
`differentiate(graph)` performs reverse accumulation in topological order.  Each operator's local gradient rule contributes `upstream * local_derivative` per input edge.  Repeated edges (e.g. `x*x`) accumulate with `Add`.  Unused parameters receive `Const(0)`.

| Rule | d/d(left) | d/d(right) |
|------|-----------|------------|
| `a+b` | `g` | `g` |
| `a-b` | `g` | `-g` |
| `a*b` | `g*b` | `g*a` |
| `a/b` | `g/b` | `-g*a/b²` |
| `a^n` (const n) | `g*n*a^(n-1)` | — |
| `a^b` (var) | `g*b*a^(b-1)` | `g*a^b*log(a)` |

### `optimizer.py`
`optimize(roots)` performs one forward topological pass.  Constant folding evaluates any operator whose inputs are all `Const` nodes, provided the result is a finite real.  Structural CSE merges duplicates via a shared `GraphBuilder`.

### `codegen.py`
`generate_code` emits two Python `def` blocks, one for the forward function and one for the gradient function.  Each IR node becomes one assignment using a fresh temporary.  `load_functions` executes the generated source in an isolated namespace.

### `compiler.py` *(Phase 3)*
`compile_source(source, inputs, parameter_types)` is the single public entry point.  It runs the full pipeline and returns a `CompileResult` dataclass with fields for tokens, AST, symbols, both IRs, gradient nodes, node counts, generated source, and (when `inputs` is provided) numerical output and gradient values.  `main_cli` implements `python -m gradlang`.

---

## CompileResult fields

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Original source text |
| `tokens` | `list[Token]` | Lexer output |
| `ast` | `FunctionDef` | Parsed AST of first function |
| `symbols` | `dict` | Symbol table `{name: Symbol}` |
| `graph` | `Graph` | Forward DAG before optimisation |
| `ir_before` | `str` | Human-readable forward IR before opt |
| `gradient_nodes` | `dict` | Raw gradient roots per parameter |
| `output_opt` | `Node` | Optimised forward output node |
| `gradient_nodes_opt` | `dict` | Optimised gradient roots |
| `ir_after` | `str` | Human-readable forward IR after opt |
| `nodes_before` | `int` | Reachable nodes (fwd+grad) before opt |
| `nodes_after` | `int` | Reachable nodes (fwd+grad) after opt |
| `forward_source` | `str` | Generated Python forward function |
| `gradient_source` | `str` | Generated Python gradient function |
| `output` | `float\|None` | Forward value (None if not executed) |
| `gradients` | `dict\|None` | Gradient values (None if not executed) |
| `parameters` | `list[str]` | Parameters in declaration order |

---

## Installation

```sh
git clone https://github.com/Ananth-2219/GradLang.git
cd GradLang
python -m unittest discover -s tests -v   # verify 101 tests pass
```

No `pip install` or virtual environment is required.  Standard library only.

---

## Testing

```sh
# All three phases (101 tests)
python -m unittest discover -s tests -v

# Individual phases
python -m unittest tests/test_phase1.py -v   # 7 tests
python -m unittest tests/test_phase2.py -v   # 6 tests
python -m unittest tests/test_phase3.py -v   # 88 tests
```

The Phase 3 suite covers:

- **Valid programs**: constants, single/multiple variables, all operators, nested parentheses, precedence and associativity, float literals, assignments, reassignment, repeated subexpressions, zero-parameter functions.
- **Invalid programs**: illegal characters, tabs, missing returns/colons, unmatched parentheses, trailing commas, duplicate parameters, undefined identifiers, use-before-definition, inconsistent indentation, function calls, incompatible vector shapes, Python-keyword function names, division by zero, log of negative base.
- **Autodiff**: all six operator rules, chain rule, shared computation nodes, repeated variable usage, multiple inputs, zero/unused gradients, power with zero/one/constant/variable exponent, gradient through assignments.
- **Finite-difference validation**: every operator at generic non-degenerate inputs; tolerance `1e-5`.
- **Optimiser**: constant folding (chain, power), CSE, invalid-constant preservation, default sharing equivalence, node count invariants.
- **CompileResult**: field presence, types, values, no-exec mode.
- **Regressions**: Phase 1 and Phase 2 test equivalents embedded.

---

## Sample input and output

**Source file** (`loss.gl`):
```
fn loss(x, w, b):
    y = w * x + b
    return (y - 1) ^ 2
```

**Command**:
```sh
python -m gradlang loss.gl x=2.0 w=0.5 b=1.0
```

**Output**:
```
forward(x=2.0, w=0.5, b=1.0) = 1.0
gradients = {'x': 1.0, 'w': 4.0, 'b': 2.0}
```

**Analytical check**: `(w*x+b-1)^2` at `x=2, w=0.5, b=1` gives `(0.5*2+1-1)^2 = 1`.  Gradients: `d/dx = 2*(w*x+b-1)*w = 2*1*0.5 = 1`, `d/dw = 2*(w*x+b-1)*x = 2*1*2 = 4`, `d/db = 2*(w*x+b-1) = 2`.

---

## Known limitations

1. **Function calls** are parsed but rejected at semantic analysis.  Their differentiation rules have not been implemented.
2. **Vector execution** is not supported.  Vector-annotated parameters pass semantic checks but the IR builder raises `ValueError` before generating code.
3. **No domain-validity pass**.  The compiler does not statically ensure that, for example, `x > 0` when computing `x^y` with variable `y` (which requires `log(x)`).  Runtime errors or domain errors surface at execution time.
4. **No type syntax**.  All variables default to scalar.  Vector annotations must be supplied programmatically via `parameter_types`.
5. **Single expression per return**.  No multi-statement returns, tuple returns, or control flow.
6. **Scalar output only**.  The function must return a single scalar value.

---

## Formal grammar (unchanged from Phase 1)

See the EBNF section above.  The Phase 1 grammar is fully preserved in Phase 3.

---

## Reverse-mode differentiation

For each node `v`, its adjoint represents `d(output)/d(v)`.  Starting from the output (adjoint = 1), nodes are visited in reverse topological order.  Each operator rule propagates `upstream * local_derivative` to each input.  If a node already has a partial adjoint, the new contribution is added via an `Add` node.  Parameters without any path to the output receive `Const(0)`.

Example — `t = w*x; output = t + t`:
- `Add` contributes `g=1` to `t` twice.
- Accumulated adjoint of `t` is `1 + 1 = 2`.
- `Mul` propagates `2*x` to `w` and `2*w` to `x`.

---

## Optimisation details

`optimize(roots)` rebuilds all reachable nodes in one topological pass:

- **Constant folding**: if all inputs to an operator are `Const` and the result is a finite real number, the node is replaced by a single `Const`.  Division-by-zero and `log` of zero are detected and left unfollowed so they surface at runtime.
- **Common subexpression elimination (CSE)**: the shared `GraphBuilder` interns nodes by `(op, inputs-tuple, type(value), value)`.  Any two nodes with identical structure and identical inputs (by identity) map to one node.  Folding constants first may expose additional duplicates.

Counts for `loss(x,w,b) = (w*x+b-1)^2`:

| | Nodes (fwd + grad) |
|-|---|
| Before optimisation | 16 |
| After optimisation  | 14 |

---

## Compiler Visualization Dashboard

GradLang includes a professional, interactive Compiler Visualization Workbench designed for live demonstration and review. It connects a React + Vite frontend directly to the Python compiler pipeline via a lightweight FastAPI backend.

### Features
1. **GradLang Code Editor**: Syntax-highlighted code editor with pre-loaded DSL examples and dynamic parameter inputs.
2. **Interactive DAG Visualization**: Powered by ReactFlow with automatic hierarchical layouts. Highlights shared computation nodes (CSE) across both forward and derivative passes. Supports view filtering for combined, forward-only, and individual parameter gradients.
3. **Telemetry & Results**: Displays forward output $f(x)$ and reverse-mode analytical gradients $\nabla f$ with microsecond compilation latency metrics.
4. **Intermediate Representation (IR)**: Side-by-side comparison of 3-address codes before and after optimization with real node reduction counts.
5. **Autodiff Adjoints Trace**: Step-by-step table tracing reverse-mode adjoint accumulation and rules applied.
6. **Finite-Difference Validation**: Central finite-difference verification comparing numerical vs analytical gradients with absolute and relative errors.
7. **Live Test Suite & Micro-Benchmarks**: Programmatic pytest execution and phase-by-phase compiler latency breakdown (Lexer, Parser, Semantic Analysis, IR Graph, Autodiff, Optimizer, Codegen, Evaluation).

### Startup Instructions

#### Step 1: Start the FastAPI Backend
```bash
# In project root: c:\GradLang
python -m uvicorn api.main:app --port 8001 --host 127.0.0.1
```
The API starts at `http://127.0.0.1:8001` (with documentation at `http://127.0.0.1:8001/docs`).

#### Step 2: Start the Vite Frontend
```bash
# In dashboard directory: c:\GradLang\dashboard
npm install
npm run dev
```
Open your browser to `http://localhost:5173`. The Vite development server automatically proxies API requests to `http://127.0.0.1:8001`.

---

## References

- Griewank, A. & Walther, A. (2008). *Evaluating Derivatives*, SIAM.
- Aho, A. V., Lam, M. S., Sethi, R., & Ullman, J. D. (2006). *Compilers: Principles, Techniques, and Tools*, 2nd ed., Addison-Wesley.
- Python Software Foundation. (2024). *Python Language Reference*, 3.12.
- Nocedal, J. & Wright, S. J. (2006). *Numerical Optimization*, 2nd ed., Springer.

