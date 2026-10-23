"""Read-only teaching data derived from compiler IR and existing autodiff rules.

These helpers do not alter compilation, optimization, or generated functions.
"""

from gradlang.autodiff import RULES
from gradlang.ir_graph import GraphBuilder, topological_sort
from gradlang.optimizer import FOLDERS


def evaluate_nodes(roots, inputs, values=None):
    """Evaluate each reachable node once, optionally extending a shared cache."""
    values = {} if values is None else values

    def visit(node):
        if node not in values:
            if node.op == "Var":
                values[node] = inputs[node.value]
            elif node.op == "Const":
                values[node] = node.value
            else:
                values[node] = FOLDERS[node.op](*(visit(child) for child in node.inputs))
        return values[node]

    for root in roots:
        visit(root)
    return values


def number(value):
    return format(value, ".6g")


DESCRIPTIONS = {
    "Var": "Read the supplied numerical value of this parameter.",
    "Const": "Use this fixed numerical constant from the IR.",
    "Add": "Add the two input values.",
    "Sub": "Subtract the second input from the first.",
    "Mul": "Multiply the two input values.",
    "Div": "Divide the first input by the second.",
    "Pow": "Raise the first input (base) to the second input (exponent).",
    "Log": "Take the natural logarithm of the input.",
}
SYMBOLS = {"Add": "+", "Sub": "−", "Mul": "×", "Div": "÷", "Pow": "^"}


def describe_node(node, values):
    """Keep raw node.value separate from its evaluated numerical value."""
    result = values[node]
    args = [values[child] for child in node.inputs]
    if node.op == "Var":
        calculation = f"{node.value} = {number(result)}"
    elif node.op == "Const":
        calculation = number(result)
    elif node.op == "Log":
        calculation = f"ln({number(args[0])}) = {number(result)}"
    else:
        operands = [f"({number(arg)})" if arg < 0 else number(arg) for arg in args]
        calculation = f"{operands[0]} {SYMBOLS[node.op]} {operands[1]} = {number(result)}"
    return {
        "evaluatedValue": result,
        "inputValues": args,
        "calculation": calculation,
        "explanation": DESCRIPTIONS[node.op],
    }


LOCAL_RULES = {
    "Add": ("Sum rule: ∂(u+v)/∂u = 1", "Sum rule: ∂(u+v)/∂v = 1"),
    "Sub": ("Difference rule: ∂(u−v)/∂u = 1", "Difference rule: ∂(u−v)/∂v = −1"),
    "Mul": ("Product rule: ∂(u×v)/∂u = v", "Product rule: ∂(u×v)/∂v = u"),
    "Div": ("Quotient rule: ∂(u/v)/∂u = 1/v", "Quotient rule: ∂(u/v)/∂v = −u/v²"),
    "Pow": ("Power rule: ∂(u^v)/∂u = v × u^(v−1) (constant exponent 0 gives 0)",
            "Variable power rule: ∂(u^v)/∂v = u^v × ln(u)"),
}


def explain_gradients(graph, inputs):
    """Explain reverse accumulation using RULES, without changing the compiler.

    Trace each input edge, including repeated uses such as x*x. Only edges leading
    to a parameter are included in that parameter's guide. Existing RULES build
    the actual contribution expressions; no separate derivative formulas execute.
    """
    order = topological_sort([graph.output])
    ids = {node: f"node_{i}" for i, node in enumerate(order)}
    dependencies = {}
    for node in order:
        dependencies[node] = ({node.value} if node.op == "Var" else
                              set().union(*(dependencies[child] for child in node.inputs)))
    builder = GraphBuilder()
    seed = builder.const(1)
    adjoints = {graph.output: seed}
    values = evaluate_nodes([graph.output], inputs)
    events = []
    for node in reversed(order):
        if node.op not in RULES or node not in adjoints:
            continue
        upstream = adjoints[node]
        contributions = RULES[node.op](builder, node, upstream)
        local_partials = RULES[node.op](builder, node, seed)
        for index, (child, contribution, local) in enumerate(zip(node.inputs, contributions, local_partials)):
            if contribution is None or not dependencies[child]:
                continue
            total = (builder.node("Add", adjoints[child], contribution)
                     if child in adjoints else contribution)
            evaluate_nodes([upstream, local, contribution, total], inputs, values)
            adjoints[child] = total
            events.append({
                "parameters": dependencies[child],
                "sourceId": ids[node],
                "targetId": ids[child],
                "op": node.op,
                "inputIndex": index,
                "inputValues": [values[arg] for arg in node.inputs],
                "rule": LOCAL_RULES[node.op][index],
                "upstream": values[upstream],
                "localDerivative": values[local],
                "contribution": values[contribution],
                "accumulated": values[total],
                "calculation": f"{number(values[upstream])} × ({number(values[local])}) = {number(values[contribution])}",
            })
    guides = {}
    for parameter, node in graph.parameters.items():
        root = adjoints.get(node, builder.const(0))
        evaluate_nodes([root], inputs, values)
        guides[parameter] = {
            "parameter": parameter,
            "value": values[root],
            "outputNodeId": ids[graph.output],
            "parameterNodeId": ids.get(node, f"unused_{parameter}"),
            "steps": [{k: v for k, v in event.items() if k != "parameters"}
                      for event in events if parameter in event["parameters"]],
            "unused": parameter not in dependencies[graph.output],
        }
    return guides
