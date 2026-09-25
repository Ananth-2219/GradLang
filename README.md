# GradLang — Phase 1

GradLang is a compiler-design lab project for a math-expression DSL. The planned
compiler will generate gradients through an explicit reverse-mode automatic
differentiation pass. **Phase 1 implements only grammar, lexing, parsing, and AST
construction.** It does not evaluate expressions, check types or names, build IR,
differentiate, or generate code.

## Files and execution

```text
GradLang/
├── gradlang/
│   ├── __init__.py
│   ├── lexer.py
│   ├── parser.py
│   └── ast_nodes.py
├── tests/
│   ├── demo_phase1.py
│   └── test_phase1.py
└── README.md
```

Use Python 3.8 or newer. No third-party dependencies are required.

```sh
python tests/demo_phase1.py
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
