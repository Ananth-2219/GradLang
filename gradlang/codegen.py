"""Emit straight-line scalar Python using a temporary for each reachable node."""

import keyword
from .ir_graph import topological_sort


OPERATORS = {"Add": "+", "Sub": "-", "Mul": "*", "Div": "/", "Pow": "**"}


def generate_code(name, parameters, output, gradients):
    parameters = list(parameters)
    for identifier in [name, "grad_" + name] + parameters:
        if not identifier.isidentifier() or keyword.iskeyword(identifier):
            raise ValueError(f"Name {identifier!r} cannot be emitted as a Python identifier")

    def emit(function_name, roots, gradient_names=None):
        used = set(parameters)
        counter = 0

        def fresh():
            nonlocal counter
            while f"_t{counter}" in used:
                counter += 1
            result = f"_t{counter}"
            used.add(result)
            return result

        lines = [f"def {function_name}({', '.join(parameters)}):"]
        nodes = topological_sort(roots)
        log_name = fresh()
        if any(node.op == "Log" for node in nodes):
            lines.append(f"    from math import log as {log_name}")
        references = {}
        for node in nodes:
            if node.op == "Var":
                references[node] = node.value
                continue
            if node.op == "Const":
                expression = repr(node.value)
            elif node.op == "Log":
                expression = f"{log_name}({references[node.inputs[0]]})"
            else:
                left, right = (references[child] for child in node.inputs)
                expression = f"{left} {OPERATORS[node.op]} {right}"
            temporary = fresh()
            lines.append(f"    {temporary} = {expression}")
            references[node] = temporary
        if gradient_names is None:
            result = references[roots[0]]
        else:
            result = "{" + ", ".join(f"{key!r}: {references[root]}"
                                      for key, root in zip(gradient_names, roots)) + "}"
        lines.append(f"    return {result}")
        return "\n".join(lines) + "\n"

    forward = emit(name, [output])
    backward = emit("grad_" + name, [gradients[key] for key in parameters], parameters)
    return forward, backward


def load_functions(name, forward_source, gradient_source):
    """Execute compiler-generated source, not arbitrary untrusted Python text."""
    namespace = {}
    exec(forward_source + "\n" + gradient_source, namespace)
    return namespace[name], namespace["grad_" + name]
