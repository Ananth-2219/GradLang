"""Reverse-mode differentiation constructs derivative expressions as a new DAG."""

from .ir_graph import GraphBuilder, topological_sort
from .optimizer import optimize


def add_rule(builder, node, upstream):
    return (upstream, upstream)


def sub_rule(builder, node, upstream):
    return (upstream, builder.node("Sub", builder.const(0), upstream))


def mul_rule(builder, node, upstream):
    left, right = node.inputs
    return (builder.node("Mul", upstream, right), builder.node("Mul", upstream, left))


def div_rule(builder, node, upstream):
    left, right = node.inputs
    numerator = builder.node("Mul", upstream, left)
    negative = builder.node("Sub", builder.const(0), numerator)
    return (builder.node("Div", upstream, right),
            builder.node("Div", negative, builder.node("Mul", right, right)))


def pow_rule(builder, node, upstream):
    base, exponent = node.inputs
    # Recognize constant expressions such as x^(1-1), not only literal powers.
    exponent = optimize([exponent])[0]
    if exponent.op == "Const":
        # Avoid spurious 0 * base^-1 when differentiating base^0 at zero.
        if exponent.value == 0:
            return (builder.const(0), None)
        if exponent.value == 1:
            return (upstream, None)
        slope = builder.node("Mul", exponent,
                             builder.node("Pow", base, builder.const(exponent.value - 1)))
        return (builder.node("Mul", upstream, slope), None)
    slope = builder.node("Mul", exponent,
                         builder.node("Pow", base, builder.node("Sub", exponent, builder.const(1))))
    # d(a^b)/db = a^b log(a); real-valued variable powers require a > 0.
    return (builder.node("Mul", upstream, slope),
            builder.node("Mul", upstream, builder.node("Mul", node, builder.node("Log", base))))


RULES = {"Add": add_rule, "Sub": sub_rule, "Mul": mul_rule,
         "Div": div_rule, "Pow": pow_rule}


def differentiate(graph):
    """Return a parameter-name -> derivative-root mapping, including unused inputs."""
    builder = GraphBuilder()
    order = topological_sort([graph.output])
    adjoints = {graph.output: builder.const(1)}
    for node in reversed(order):
        if node.op in ("Var", "Const") or node not in adjoints:
            continue
        contributions = RULES[node.op](builder, node, adjoints[node])
        for child, contribution in zip(node.inputs, contributions):
            if contribution is None or child.op == "Const":
                continue
            # Each incoming edge contributes, including repeated edges such as x*x.
            if child in adjoints:
                contribution = builder.node("Add", adjoints[child], contribution)
            adjoints[child] = contribution
    return {name: adjoints.get(node, builder.const(0)) for name, node in graph.parameters.items()}
