"""Identity-based DAG nodes with optional structural interning."""

from dataclasses import dataclass
from .ast_nodes import Assign, BinOp, Num, Return, UnaryOp, Var
from .semantic_analysis import analyze


@dataclass(eq=False, frozen=True)
class Node:
    op: str
    inputs: tuple = ()
    value: object = None


class GraphBuilder:
    def __init__(self, share=True):
        self.share = share
        self.cache = {}

    def node(self, op, *inputs, value=None):
        # Children are already canonical, so their identities form structural keys.
        key = (op, inputs, type(value), value)
        if self.share and key in self.cache:
            return self.cache[key]
        result = Node(op, inputs, value)
        if self.share:
            self.cache[key] = result
        return result

    def const(self, value):
        return self.node("Const", value=value)


@dataclass
class Graph:
    name: str
    parameters: dict
    output: Node


def topological_sort(roots):
    """Inputs precede consumers; shared nodes occur exactly once."""
    visited, order = set(), []

    def visit(node):
        if node in visited:
            return
        visited.add(node)
        for child in node.inputs:
            visit(child)
        order.append(node)

    for root in roots:
        visit(root)
    return order


def format_graph(roots):
    nodes = topological_sort(roots)
    labels = {node: f"n{i}" for i, node in enumerate(nodes)}
    lines = []
    for node in nodes:
        detail = ", ".join(labels[child] for child in node.inputs) if node.inputs else repr(node.value)
        lines.append(f"{labels[node]} = {node.op}({detail})")
    return "\n".join(lines)


OPERATORS = {"+": "Add", "-": "Sub", "*": "Mul", "/": "Div", "^": "Pow"}


def build_graph(function, parameter_types=None, share=True):
    symbols = analyze(function, parameter_types)
    if any(symbol.shape for symbol in symbols.values()) or any(
        symbol.shape for symbol in (parameter_types or {}).values()
    ):
        raise ValueError("Phase 2 code generation supports scalars only; vector shapes are checked but not lowered")
    builder = GraphBuilder(share)
    parameters = {name: builder.node("Var", value=name) for name in function.params}
    environment = dict(parameters)

    def lower(expr):
        if isinstance(expr, Num):
            return builder.const(expr.value)
        if isinstance(expr, Var):
            return environment[expr.name]
        if isinstance(expr, UnaryOp):
            return builder.node("Sub", builder.const(0), lower(expr.operand))
        if isinstance(expr, BinOp):
            return builder.node(OPERATORS[expr.operator], lower(expr.left), lower(expr.right))
        raise ValueError(f"Unsupported expression: {expr!r}")

    for statement in function.body:
        if isinstance(statement, Assign):
            environment[statement.name] = lower(statement.value)
        elif isinstance(statement, Return):
            return Graph(function.name, parameters, lower(statement.value))
    raise ValueError("Function has no return")
