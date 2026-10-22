# GradLang — Final Review Documentation

**Compiler Design Laboratory Project**
**Student:** Ananth-2219
**Repository:** https://github.com/Ananth-2219/GradLang

---

## 1. Introduction

GradLang is a domain-specific language (DSL) implemented as a compiler project for the Compiler Design Laboratory.  The language accepts mathematical expressions involving scalar variables and arithmetic operators, compiles them through a full compiler pipeline, and produces Python functions for both forward evaluation and exact gradient computation via reverse-mode automatic differentiation.

The project implements all classical compiler phases — lexical analysis, parsing, semantic analysis, intermediate representation, optimisation, and code generation — and adds a mathematically rigorous automatic differentiation pass that generates gradient programs symbolically rather than numerically.

---

## 2. Problem Statement

Given a scalar mathematical expression defined as a GradLang program, automatically derive and execute:

1. A **forward function** that evaluates the expression at given input values.
2. A **gradient function** that computes the partial derivative of the output with respect to every input parameter, computed using the reverse-mode (backpropagation) algorithm.

The derivatives must be symbolically exact (to floating-point precision) and must agree with central finite-difference approximations to within tolerance `1e-5`.

---

## 3. Objectives

- Implement a complete, working compiler for the GradLang grammar.
- Correctly handle operator precedence, associativity, and parentheses.
- Perform semantic validation with clear, positioned error messages.
- Construct a shared computation DAG for the intermediate representation.
- Apply the reverse-mode differentiation algorithm with correct multi-edge accumulation.
- Optimise the IR using constant folding and common subexpression elimination.
- Generate correct, readable Python code and execute it safely.
- Provide a unified, single-call pipeline for integration and testing.
- Achieve 100% pass rate on a comprehensive automated test suite.
- Provide reproducible performance measurements.

---

## 4. Background Study

### 4.1 Compiler Architecture

A typical compiler pipeline proceeds through:

1. **Lexical analysis** — source characters to tokens.
2. **Syntax analysis** — tokens to abstract syntax tree.
3. **Semantic analysis** — type/scope checking.
4. **Intermediate representation** — language-independent graph.
5. **Optimisation** — IR transformation for efficiency.
6. **Code generation** — target language emission.

GradLang implements all six phases with an additional differentiation pass between IR construction and optimisation.

### 4.2 Reverse-Mode Automatic Differentiation

Reverse-mode AD, also called backpropagation in machine learning, computes gradients of a scalar output with respect to all inputs in a single backward pass.  The algorithm:

1. Evaluates the forward computation and records the computation graph.
2. Initialises the adjoint of the output to 1.
3. Visits nodes in reverse topological order.
4. For each node, distributes the accumulated adjoint to its inputs according to the local derivative rule.
5. Sums contributions along all paths using the multivariate chain rule.

This is more efficient than forward-mode AD when the output is a single scalar and the inputs are many — the typical case in loss function optimisation.

### 4.3 Structural CSE

Common subexpression elimination identifies computations that produce identical results.  In a DAG-based IR, structural hashing achieves this automatically: two nodes with the same operator and the same (by identity) input nodes are represented by a single object.  When construction-time sharing is disabled for demonstration, a post-hoc CSE pass rebuilds the graph using a shared `GraphBuilder`.

---

## 5. System Design

### 5.1 Architecture Diagram

```
+-------------------+
|   Source Text     |
+--------+----------+
         |
         v
+--------+----------+
|  Lexer (lexer.py) |  -> Token stream (INDENT/DEDENT/NEWLINE/EOF)
+--------+----------+
         |
         v
+--------+----------+
| Parser (parser.py)|  -> AST (FunctionDef, Assign, Return, BinOp, ...)
+--------+----------+
         |
         v
+--------+----------+
| Semantic Analysis |  -> Symbol table {name: Symbol(kind, shape)}
| (semantic_analysis|
|  symbol_table.py) |
+--------+----------+
         |
         v
+--------+----------+
| IR Builder        |  -> Graph(name, parameters, output)
| (ir_graph.py)     |     Node DAG (Var, Const, Add, Sub, Mul, Div, Pow)
+--------+----------+
         |
         v
+--------+----------+
| Autodiff          |  -> {param: derivative_root_Node}
| (autodiff.py)     |
+--------+----------+
         |
         v
+--------+----------+
| Optimiser         |  -> Optimised Node roots
| (optimizer.py)    |     (constant folding + CSE)
+--------+----------+
         |
         v
+--------+----------+
| Code Generator    |  -> Python source strings
| (codegen.py)      |
+--------+----------+
         |
         v
+--------+----------+
| Execution         |  -> forward(**inputs), gradients(**inputs)
| (load_functions)  |
+-------------------+
```

### 5.2 IR Node Types

| Op | Inputs | Meaning |
|----|--------|---------|
| `Var` | — | Named parameter |
| `Const` | — | Numeric literal |
| `Add` | left, right | Addition |
| `Sub` | left, right | Subtraction |
| `Mul` | left, right | Multiplication |
| `Div` | left, right | Division |
| `Pow` | base, exp | Exponentiation |
| `Log` | arg | Natural logarithm (derivative IR only) |

---

## 6. Methodology

### 6.1 Grammar Design

The grammar uses explicit precedence layers (additive → multiplicative → unary → power → primary) to encode precedence without ambiguity.  Left-associativity is implemented by loops within each layer; right-associativity for `^` by recursion through the unary layer.

### 6.2 Lexer Implementation

A line-oriented scanner tracks indentation with a stack.  Each line's leading space count is compared to the stack top: increases push `INDENT`, decreases pop `DEDENT` tokens.  Numbers and identifiers are matched with compiled regular expressions.  Keywords are distinguished from identifiers after matching.

### 6.3 Parser Implementation

A pure recursive-descent parser with one method per grammar rule.  `expect(kind)` consumes a required token or raises `ParseError` with line and column.  The parser emits AST nodes annotated with source line numbers for diagnostic use.

### 6.4 Semantic Analysis

A single ordered walk (no symbol table pre-population):

- Each assignment's RHS is checked before the target name is inserted.
- This correctly rejects `y = z + x; z = 1` where `z` is used before defined.
- Duplicate parameters and unsupported operations (function calls, unsupported operators) are rejected with the offending expression and line number.
- Shape inference propagates scalar broadcast rules for elementwise operators.

### 6.5 IR Construction

`build_graph` lowers an AST to a `Graph` by recursively mapping AST expressions to IR nodes.  A `GraphBuilder` maintains an intern cache keyed by `(op, inputs-tuple, type(value), value)`, providing structural sharing at construction time.

### 6.6 Reverse-Mode Differentiation

The differentiation pass:

1. Performs topological sort of the forward graph.
2. Initialises `adjoints[output] = Const(1)`.
3. Iterates nodes in reverse order; for each node with an adjoint, applies the local rule to produce contributions for each input.
4. Accumulates contributions via `Add` nodes (never overwrites partial adjoints).
5. Returns `{param_name: adjoint_node}` for all parameters; unused parameters get `Const(0)`.

Key special cases:
- `Pow` with constant exponent 0 → derivative is `Const(0)`.
- `Pow` with constant exponent 1 → derivative is `upstream`.
- `Pow` with variable exponent → derivative w.r.t. exponent requires `Log(base)`.

### 6.7 Optimisation

`optimize(roots)` rebuilds the reachable subgraph in topological order using a fresh shared `GraphBuilder`.  Constant folding is attempted for every operator node whose optimised children are all `Const`.  Invalid folds (zero division, `log` of non-positive) are silently skipped so the runtime error is preserved.  CSE follows naturally from structural sharing in the new builder.

### 6.8 Code Generation

Each IR node in topological order becomes one Python assignment.  `Var` nodes emit their parameter name directly.  `Const` nodes emit `repr(value)`.  `Log` nodes emit `log(arg)` with a `from math import log` header.  All other nodes emit the two-input expression.  The gradient function returns a dictionary keyed by parameter names.

---

## 7. Compiler Design Concepts Demonstrated

| Concept | Where implemented |
|---------|-------------------|
| Deterministic finite automaton (via regex) | Lexer |
| Context-free grammar | EBNF in README; parser methods |
| Recursive-descent parsing | `parser.py` |
| Parse error with position | `ParseError`, `LexerError` |
| Abstract syntax tree | `ast_nodes.py` |
| Symbol table | `symbol_table.py` |
| Semantic analysis | `semantic_analysis.py` |
| DAG-based IR | `ir_graph.py` |
| Topological sort | `ir_graph.topological_sort` |
| Constant folding | `optimizer.py` |
| Common subexpression elimination | `optimizer.py` (GraphBuilder interning) |
| Code generation | `codegen.py` |
| Reverse-mode automatic differentiation | `autodiff.py` |
| Chain rule / multivariate accumulation | `autodiff.py` |

---

## 8. Implementation

### Phase 1 (Lexer + Parser)

- `tokenize(source)` — full layout-sensitive tokeniser.
- `Parser.parse()` — recursive-descent, returns `List[FunctionDef]`.
- 7 unit tests, covering tree shape, precedence, associativity, layout, keyword boundaries, positioned errors, and malformed programs.

### Phase 2 (IR + Autodiff + Optimiser + Codegen)

- `build_symbol_table` — use-before-definition, shape inference.
- `build_graph` — AST to DAG lowering.
- `differentiate` — reverse-mode accumulation with all five operator rules.
- `optimize` — constant folding + CSE.
- `generate_code`, `load_functions` — Python code emission and loading.
- 6 unit tests covering symbols/errors, shapes, CSE/folding, finite differences, edge cases, and codegen safety.

### Phase 3 (Unified Pipeline + Comprehensive Tests + Demo + CLI)

**New files:**
- `gradlang/compiler.py` — `compile_source()`, `CompileResult`, `main_cli()`, `_validate_inputs()`, `_format_tokens()`, `_format_ast()`.
- `gradlang/__main__.py` — CLI entry point.
- `tests/test_phase3.py` — 88 tests across 7 test classes.
- `tests/demo_phase3.py` — 11-step final review demonstration.

**Modified:**
- `gradlang/__init__.py` — updated docstring.
- `README.md` — complete rewrite covering all three phases.

---

## 9. Testing and Results

### 9.1 Test suite summary

| Phase | File | Tests | Status |
|-------|------|-------|--------|
| Phase 1 | `test_phase1.py` | 7 | All pass |
| Phase 2 | `test_phase2.py` | 6 | All pass |
| Phase 3 | `test_phase3.py` | 88 | All pass |
| **Total** | | **101** | **101 / 101** |

Run: `python -m unittest discover -s tests -v`

### 9.2 Phase 3 test breakdown

| Class | Tests | Covers |
|-------|-------|--------|
| `TestValidPrograms` | 22 | All valid expressions |
| `TestInvalidPrograms` | 21 | All error conditions |
| `TestAutodiff` | 19 | Differentiation rules |
| `TestOptimiser` | 9 | Folding + CSE |
| `TestCompileResult` | 10 | API structure |
| `TestPhase1Regression` | 2 | Phase 1 no-regression |
| `TestPhase2Regression` | 3 | Phase 2 no-regression |

### 9.3 Gradient correctness results

Expressions tested against central finite differences (`ε = 1e-6`, tolerance `1e-5`):

| Expression | Passes |
|------------|--------|
| `x+y` | Yes |
| `x-y` | Yes |
| `x*y` | Yes |
| `x/y` | Yes |
| `x^3` | Yes |
| `x^y` | Yes |
| `-x` | Yes |
| `x*x+x*x` | Yes |
| `(x*y+1)^2` | Yes |

For `loss(x,w,b) = (w*x+b-1)^2` at `x=2, w=0.5, b=1`:

| Parameter | Analytical | Numerical | Error |
|-----------|-----------|-----------|-------|
| x | 1.00000000 | 1.00000000 | 1.40e-10 |
| w | 4.00000000 | 4.00000000 | 5.95e-11 |
| b | 2.00000000 | 2.00000000 | 3.35e-10 |

### 9.4 Optimisation results

For `loss(x,w,b) = (w*x+b-1)^2` (forward + all gradient roots combined):

| Metric | Value |
|--------|-------|
| Nodes before optimisation | 16 |
| Nodes after optimisation  | 14 |
| Nodes eliminated          |  2 |

For `shared(w,x) = w*x + w*x` (CSE demonstration, sharing disabled):

| Metric | Value |
|--------|-------|
| Nodes before CSE | 5 |
| Nodes after CSE  | 4 |

### 9.5 Performance measurements (measured on student machine)

| Metric | Value |
|--------|-------|
| Compilation time (avg, 500 trials) | ~0.3 ms / compile |
| Forward function call (avg, 50 000 trials) | ~190 ns / call |

---

## 10. Conclusion

GradLang successfully implements a complete compiler pipeline for a mathematical DSL, from source text to executable Python functions with analytically correct gradients.  All 101 automated tests pass.  The reverse-mode differentiation pass produces gradients that agree with numerical finite-difference approximations to better than 1e-10 at the demonstration inputs.  The optimiser measurably reduces node counts through constant folding and structural CSE without altering numerical results.

The project demonstrates the practical application of compiler design theory — grammar design, recursive-descent parsing, symbol tables, IR construction, DAG optimisation, and code generation — in a setting where the "target language" is an autodiff gradient program rather than assembly.

---

## 11. Future Enhancements

1. **Function calls** — implement derivative rules for built-in functions (sin, cos, exp, log) and user-defined recursive functions.
2. **Vector/matrix support** — extend IR lowering and code generation for elementwise and dot-product operations.
3. **Forward-mode AD** — add a dual-number pass for Jacobian-vector products.
4. **Higher-order derivatives** — allow differentiation of the gradient program itself.
5. **Type inference** — infer scalar vs. vector from context rather than requiring external annotations.
6. **Error recovery** — continue parsing after a syntax error to report multiple errors.
7. **Interactive REPL** — a read-evaluate-print loop for exploratory computation.

---

## 12. References

1. Aho, A. V., Lam, M. S., Sethi, R., & Ullman, J. D. (2006). *Compilers: Principles, Techniques, and Tools*, 2nd ed. Addison-Wesley.
2. Griewank, A., & Walther, A. (2008). *Evaluating Derivatives: Principles and Techniques of Algorithmic Differentiation*, 2nd ed. SIAM.
3. Baydin, A. G., Pearlmutter, B. A., Radul, A. A., & Siskind, J. M. (2018). Automatic differentiation in machine learning: a survey. *Journal of Machine Learning Research*, 18, 1–43.
4. Nocedal, J., & Wright, S. J. (2006). *Numerical Optimization*, 2nd ed. Springer.
5. Python Software Foundation. (2024). *The Python Language Reference*, version 3.12. Retrieved from https://docs.python.org/3/.
6. Appel, A. W. (2004). *Modern Compiler Implementation in Java*, 2nd ed. Cambridge University Press.
