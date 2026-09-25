# GradLang — Phases 1 and 2

GradLang is a compiler-design lab project for a math-expression DSL. The planned
compiler generates gradients through an explicit reverse-mode automatic
differentiation pass. Phase 1 provides grammar, lexing, parsing, and AST
construction. Phase 2 adds semantic checks, a shared computation DAG,
hand-written reverse-mode differentiation, optimization, and scalar Python codegen.

## Files and execution

```text
GradLang/
├── gradlang/
│   ├── __init__.py
│   ├── lexer.py
│   ├── parser.py
│   ├── ast_nodes.py
│   ├── symbol_table.py
│   ├── semantic_analysis.py
│   ├── ir_graph.py
│   ├── autodiff.py
│   ├── optimizer.py
│   └── codegen.py
├── tests/
│   ├── demo_phase1.py
│   ├── test_phase1.py
│   ├── demo_phase2.py
│   └── test_phase2.py
└── README.md
```

Use Python 3.8 or newer. No third-party dependencies are required.

```sh
python tests/demo_phase1.py
python tests/demo_phase2.py
python -m unittest discover -s tests -v
```

The demo parses this program, prints nested dataclass representations, and reports
a deliberately malformed expression with its line and column:

```text
fn loss(x, w, b):
    y = w * x + b
    return (y - 1) ^ 2
```

## Formal grammar

This EBNF describes the token stream. Quoted strings are terminals, `=` defines
a production, `,` concatenates, `|` selects alternatives, `{ ... }` means zero or
more repetitions, and `[ ... ]` means optional. A semicolon ends a production.
`NEWLINE`, `INDENT`, `DEDENT`, and `EOF` are lexer-generated tokens.

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

Lexical productions use character terminals; `IDENT` excludes the exact reserved
words `fn` and `return`:

```ebnf
IDENT          = letter_or_underscore, { letter_or_underscore | digit } ;
NUMBER         = (digits, [ ".", digits ] | ".", digits),
                 [ ("e" | "E"), [ "+" | "-" ], digits ] ;
digits         = digit, { digit } ;
digit          = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
```

`letter_or_underscore` is an ASCII letter (`A`–`Z`, `a`–`z`) or `_`.
Identifiers are case-sensitive. The lexer takes the longest identifier or number
matching its lexical rule; keywords are classified after reading an identifier.
Numbers include `12`, `1.25`, `.5`, and `2e-3`. A trailing decimal point (`1.`)
is unsupported. A sign is an operator, except inside a numeric exponent.
Integer literals become Python `int`; decimal/exponent literals become Python
`float`, with ordinary floating-point rounding and range limits.

### Layout rules

- Spaces separate tokens. Tabs are rejected, including on otherwise blank lines.
- Blank or spaces-only lines produce no tokens and do not change indentation.
- Every nonblank physical line produces `NEWLINE`, even without a final newline.
- Leading spaces are compared with an indentation stack initially containing zero.
  A larger count produces `INDENT`. A smaller count must match an earlier level
  and produces the required `DEDENT` tokens. EOF closes remaining indentation.
- Function headers are at column one. Body lines share one positive indentation
  level. Four spaces are recommended; any consistent positive width is accepted.
- CRLF and CR line endings are normalized to LF. Expressions and headers must
  fit on one physical line; parentheses do not enable line continuation.
- Positions are one-based character columns, including leading spaces. Illegal
  characters and inconsistent indentation raise `LexerError`; malformed token
  sequences raise `ParseError`. Both derive from `SyntaxError`.

## Grammar decisions and limits

1. A program is a nonempty list of functions. Each function accepts zero or more
   named parameters, zero or more assignments, and exactly one final return.
   This models a straight-line math function without control-flow analysis.
2. `+` and `-` share precedence and associate left; `*` and `/` share higher
   precedence and also associate left. Thus `a-b-c` means `(a-b)-c` and `a/b*c`
   means `(a/b)*c`. Parser loops build these left subtrees explicitly.
3. `^` means exponentiation, not XOR. It associates right, following mathematical
   convention: `a^b^c` means `a^(b^c)`.
4. Exponentiation binds above unary minus on its left: `-x^2` means `-(x^2)`.
   The exponent accepts a unary expression, so `x^-2` means `x^(-2)`. Recursive
   unary minus also accepts `--x`. Unary plus is outside this grammar.
5. Parentheses override precedence. Named calls such as `f(x, g(y))` are primary
   expressions and support zero or more arguments. Only identifiers can be
   callees; chained calls and calls on arbitrary expressions are unsupported.
6. Assignments are statements, not expressions. Only a single identifier may be
   assigned. Trailing commas, bare expression statements, nested functions,
   comments, strings, vector literals, indexing, and control flow are omitted.
   Scalar/vector meaning belongs to later semantic work; Phase 1 names and calls
   carry no type information.
7. The grammar has no unresolved syntactic ambiguity. Precedence layers choose
   operator grouping; one-token lookahead distinguishes a variable from a call.
   Indentation delimits bodies. Assignment and return start with distinct tokens.
8. Undefined names, duplicate parameters, reassignment, call arity, and invalid
   mathematical operations are intentionally not checked. These are semantic
   questions, not parsing errors.

## Implementation walkthrough

`tokenize(source)` returns `Token(kind, value, line, column)` objects. It scans
one line at a time, emits layout tokens, then recognizes numbers, names, and
single-character punctuation. It appends one EOF token.

`Parser(tokens).parse()` returns a list of `FunctionDef` nodes. Each parser method
mirrors an EBNF production. `expect()` consumes a required token or reports the
current token's position. Loops implement left associativity; recursion implements
unary operators and right-associative powers.

`ast_nodes.py` contains the eight required data classes. A function stores its
parameter names and ordered statements. Expressions store child expressions,
operators, names, or numeric values. Parentheses affect tree shape and therefore
need no separate AST node. The AST stores syntax only; no backward pass runs.

## Phase 2 pipeline and APIs

The Phase 1 grammar remains unchanged. AST nodes now retain source line numbers;
these metadata fields do not change structural equality in the Phase 1 tests.
The restrictions above describe parsing; the additional semantic checks below
apply when compiling a function through Phase 2.

1. `build_symbol_table(function, parameter_types=None)` in `symbol_table.py`
   maps names to `Symbol(kind, shape)`. It walks statements in order, rejects
   duplicate parameters and uses before definition, and infers assignment shapes.
2. `analyze(function, parameter_types=None)` in `semantic_analysis.py` is the
   public semantic entrypoint. It shares the symbol-building walk so a later
   assignment cannot accidentally authorize an earlier reference. Diagnostics
   include the offending expression and its source line.
3. `build_graph(function, parameter_types=None, share=True)` lowers checked AST
   nodes to a DAG. Assignments update the name environment; earlier nodes keep
   their original inputs. Unary minus lowers to `Sub(Const(0), operand)`.
   `format_graph([root])` prints nodes in topological order.
4. `differentiate(graph)` returns a dictionary mapping every original parameter
   name to its derivative root. Unused parameters receive zero.
5. `optimize(roots)` returns new roots after constant folding and structural CSE.
   Passing forward and derivative roots together permits sharing across them.
6. `generate_code(name, parameters, output, gradients)` returns forward and
   gradient source strings. `load_functions(name, forward_source, gradient_source)`
   executes those strings and returns both Python functions. Only execute trusted,
   compiler-generated code. DSL names that are Python keywords are rejected.

`tests/demo_phase2.py` shows all passes in order and prints the generated code.
For `x=2, w=0.5, b=1`, the forward result is `1` and the gradient dictionary is
`{'x': 1, 'w': 4, 'b': 2}`. The demo independently checks `w` and `b` with central
finite differences using epsilon `1e-6` and absolute tolerance `1e-5`.

### Shapes and supported operations

Parameters default to `Symbol('scalar', ())`. Explicit metadata can be supplied
as `{'x': Symbol('vector', (3,))}` without adding type syntax to the language.
Shape inference accepts equal shapes or a scalar broadcast against another shape;
unequal non-scalar shapes fail. All binary operators are elementwise for this
shape policy. The current backend rejects vector lowering explicitly; numerical
execution and differentiation are scalar-only. Function calls remain parseable
but are rejected by Phase 2 until call semantics and derivative rules are defined.

Scalar execution uses Python numeric behavior. Division requires a nonzero
denominator. Differentiation assumes real inputs at differentiable points.
Variable exponents require a positive base: their derivative needs `log(base)`.
An internal `Log` node therefore extends the derivative IR; it is not a new DSL
function. Constant powers use the ordinary power rule and avoid logarithms,
including explicit handling of exponents zero and one. Other powers retain their
ordinary real-domain restrictions. No domain-proof pass is implemented.

### Reverse-mode accumulation

For each node `v`, its adjoint represents `d(output)/d(v)`. The output adjoint
starts at one. Reverse topological order visits every consumer before its inputs.
Each operator rule contributes `upstream * local_derivative` along each input
edge. If an input already has an adjoint, the pass constructs an `Add` node to
sum the new contribution with the previous one. It never overwrites a contribution.

For `t=w*x; output=t+t`, the Add contributes one twice to the same `t` node.
The accumulated adjoint of `t` is two before Mul is processed, so the parameter
gradients are `2*x` and `2*w`. Repeated edges within one operator, such as `x*x`,
also contribute separately. This implements the multivariate chain rule.

The dispatch table in `autodiff.py` separates these local rules:

| Operation | Contribution to left input | Contribution to right input |
|---|---|---|
| `a+b` | `g` | `g` |
| `a-b` | `g` | `-g` |
| `a*b` | `g*b` | `g*a` |
| `a/b` | `g/b` | `-g*a/(b*b)` |
| `a^b` | `g*b*a^(b-1)` | `g*a^b*log(a)` for variable exponents |

Here `g` is the accumulated upstream adjoint. Constant inputs do not require
gradient propagation. The pass constructs expressions rather than evaluating
derivatives; optimization and code generation consume those expressions later.

### What CSE removes

For `return w*x + w*x`, construction with `share=False` produces five reachable
nodes: two variables, two Mul nodes, and one Add. CSE identifies both Mul nodes
by the same operator and canonical inputs. It merges them, producing **four**
nodes, with both Add inputs pointing to the same Mul.

Normal construction uses structural hashing already and produces four nodes;
running CSE then leaves four. The demo deliberately disables construction sharing
to make the reduction visible. Counts include all nodes reachable from the output.
Operand order matters: `w*x` and `x*w` are not merged by algebraic reasoning.
Constant folding can expose further duplicates; tests cover this case too.
Invalid constant operations are retained so optimization preserves runtime errors.
