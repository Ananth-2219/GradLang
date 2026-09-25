"""Build symbols in statement order, checking definitions and propagating shapes."""

from dataclasses import dataclass
from .ast_nodes import Assign, BinOp, Call, Num, UnaryOp, Var


class SemanticError(ValueError):
    pass


@dataclass(frozen=True)
class Symbol:
    kind: str = "scalar"
    shape: tuple = ()

    def __post_init__(self):
        if self.kind not in ("scalar", "vector"):
            raise ValueError("Kind must be scalar or vector")
        if not isinstance(self.shape, tuple) or any(type(n) is not int or n <= 0 for n in self.shape):
            raise ValueError("Shape must be a tuple of positive integer dimensions")
        if (self.kind == "scalar" and self.shape) or (self.kind == "vector" and len(self.shape) != 1):
            raise ValueError("Scalars have shape (); vectors have shape (length,)")


def describe(expr):
    """Source-like text makes diagnostics easier to explain than object reprs."""
    if isinstance(expr, Var):
        return expr.name
    if isinstance(expr, Num):
        return str(expr.value)
    if isinstance(expr, UnaryOp):
        return f"(-{describe(expr.operand)})"
    if isinstance(expr, BinOp):
        return f"({describe(expr.left)} {expr.operator} {describe(expr.right)})"
    if isinstance(expr, Call):
        return f"{expr.name}({', '.join(map(describe, expr.arguments))})"
    return repr(expr)


def fail(expr, message):
    raise SemanticError(f"{message} in {describe(expr)!r} at line {expr.line or 'unknown'}")


def compatible(left, right, expr):
    """Elementwise operations allow equal shapes or scalar broadcasting only."""
    if left.shape == right.shape:
        return left
    if not left.shape:
        return right
    if not right.shape:
        return left
    fail(expr, f"Incompatible shapes {left.shape} and {right.shape}")


def infer_expression(expr, symbols):
    if isinstance(expr, Num):
        return Symbol()
    if isinstance(expr, Var):
        if expr.name not in symbols:
            fail(expr, f"Variable {expr.name!r} used before definition")
        return symbols[expr.name]
    if isinstance(expr, UnaryOp):
        if expr.operator != "-":
            fail(expr, "Unsupported unary operator")
        return infer_expression(expr.operand, symbols)
    if isinstance(expr, BinOp):
        if expr.operator not in ("+", "-", "*", "/", "^"):
            fail(expr, "Unsupported binary operator")
        return compatible(infer_expression(expr.left, symbols),
                          infer_expression(expr.right, symbols), expr)
    if isinstance(expr, Call):
        fail(expr, "Function calls are not supported by the Phase 2 backend")
    fail(expr, "Unsupported expression")


def build_symbol_table(function, parameter_types=None):
    """Optional parameter_types maps parameter names to explicit Symbol objects."""
    parameter_types = parameter_types or {}
    unknown = set(parameter_types) - set(function.params)
    if unknown:
        raise SemanticError(f"Unknown parameter annotations: {sorted(unknown)} at line {function.line}")
    symbols = {}
    for name in function.params:
        if name in symbols:
            raise SemanticError(f"Duplicate parameter {name!r} at line {function.line}")
        symbol = parameter_types.get(name, Symbol())
        if not isinstance(symbol, Symbol):
            raise TypeError("Parameter annotations must be Symbol objects")
        symbols[name] = symbol
    for statement in function.body:
        # Inspect the RHS before introducing an assignment target: x = x+1
        # requires an earlier definition of x.
        inferred = infer_expression(statement.value, symbols)
        if isinstance(statement, Assign):
            symbols[statement.name] = inferred
    return symbols
