"""Rebuild reachable nodes with constant folding and structural CSE."""

import math
import operator
from .ir_graph import GraphBuilder, topological_sort


FOLDERS = {"Add": operator.add, "Sub": operator.sub, "Mul": operator.mul,
           "Div": operator.truediv, "Pow": operator.pow, "Log": math.log}


def optimize(roots):
    """Optimize multiple roots together so forward/gradient expressions can share."""
    builder, replacements = GraphBuilder(), {}
    for node in topological_sort(roots):
        children = tuple(replacements[child] for child in node.inputs)
        replacement = None
        if node.op in FOLDERS and all(child.op == "Const" for child in children):
            try:
                value = FOLDERS[node.op](*(child.value for child in children))
                if isinstance(value, (int, float)) and math.isfinite(value):
                    replacement = builder.const(value)
            except (ArithmeticError, ValueError):
                # Leave invalid constant operations to retain their runtime errors.
                pass
        replacements[node] = replacement or builder.node(node.op, *children, value=node.value)
    return [replacements[root] for root in roots]
