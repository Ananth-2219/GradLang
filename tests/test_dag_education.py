"""DAG teaching data must agree with the actual compiled functions."""

import math

import pytest
from fastapi.testclient import TestClient

from api.main import app, serialize_dag
from api.dag_education import evaluate_nodes, explain_gradients
from gradlang.codegen import generate_code, load_functions
from gradlang.compiler import compile_source
from gradlang.ir_graph import GraphBuilder, topological_sort


CASES = [
    ("fn loss(x, w, b):\n    return (w * x + b - 1) ^ 2\n", {"x": 2, "w": 0.5, "b": 1}),
    ("fn f(x, y):\n    return (x + y) / (x - y)\n", {"x": 5, "y": 2}),
    ("fn f(x):\n    return x * x + x\n", {"x": -3}),
    ("fn f(x, y):\n    return x ^ y\n", {"x": 2, "y": 3}),
    ("fn f(x, y):\n    return x\n", {"x": 0, "y": 4}),
    ("fn f(x):\n    return x ^ 0\n", {"x": 0}),
    ("fn f():\n    return 2 * 3 + 1\n", {}),
]


@pytest.mark.parametrize("source,inputs", CASES)
def test_every_evaluated_node_matches_generated_python(source, inputs):
    result = compile_source(source, inputs)
    roots = [result.graph.output, result.output_opt, *result.gradient_nodes_opt.values()]
    values = evaluate_nodes(roots, inputs)
    for node in topological_sort(roots):
        forward_src, gradient_src = generate_code("node_value", result.parameters, node, result.gradient_nodes_opt)
        generated, _ = load_functions("node_value", forward_src, gradient_src)
        assert values[node] == pytest.approx(generated(**inputs))
    assert values[result.output_opt] == pytest.approx(result.output)
    for parameter, root in result.gradient_nodes_opt.items():
        assert values[root] == pytest.approx(result.gradients[parameter])


@pytest.mark.parametrize("source,inputs", CASES)
def test_chain_rule_contributions_accumulate_to_generated_gradients(source, inputs):
    result = compile_source(source, inputs)
    guides = explain_gradients(result.graph, inputs)
    assert set(guides) == set(result.parameters)
    for param, guide in guides.items():
        assert guide["value"] == pytest.approx(result.gradients[param])
        totals = {guide["outputNodeId"]: 1.0}
        for step in guide["steps"]:
            assert step["upstream"] == pytest.approx(totals[step["sourceId"]])
            assert step["contribution"] == pytest.approx(step["upstream"] * step["localDerivative"])
            totals[step["targetId"]] = totals.get(step["targetId"], 0) + step["contribution"]
            assert step["accumulated"] == pytest.approx(totals[step["targetId"]])
            assert step["rule"] and step["calculation"]
        assert totals.get(guide["parameterNodeId"], 0) == pytest.approx(guide["value"])


def test_node_calculations_explain_inputs_and_keep_literal_values():
    builder = GraphBuilder()
    x, y = builder.node("Var", value="x"), builder.node("Var", value="y")
    mul = builder.node("Mul", x, y)
    root = builder.node("Add", mul, builder.const(1))
    dag = serialize_dag([root], {root: "Output"}, inputs={"x": 2, "y": 3})
    nodes = dag["nodes"]
    assert nodes[0]["value"] == "x"  # Existing API field remains a variable name.
    assert nodes[0]["evaluatedValue"] == 2
    product = next(n for n in nodes if n["op"] == "Mul")
    assert product["inputValues"] == [2, 3]
    assert product["calculation"] == "2 × 3 = 6"
    assert "Multiply" in product["explanation"]
    assert nodes[-1]["calculation"] == "6 + 1 = 7"
    assert nodes[-1]["evaluatedValue"] == 7


def test_repeated_input_edges_are_explained_as_uses_not_distinct_consumers():
    result = compile_source("fn f(x):\n    return x * x\n", {"x": 3})
    dag = serialize_dag([result.graph.output], inputs={"x": 3})
    shared = next(n for n in dag["nodes"] if n["op"] == "Var")
    assert shared["consumerCount"] == 2
    assert len(set(shared["consumers"])) == 1
    assert "2 input uses" in shared["sharedExplanation"]
    guide = explain_gradients(result.graph, {"x": 3})["x"]
    assert [step["contribution"] for step in guide["steps"]] == [3, 3]
    assert guide["value"] == 6


def test_variable_power_log_values_and_rules_are_correct():
    result = compile_source("fn f(x, y):\n    return x ^ y\n", {"x": 2, "y": 3})
    dag = serialize_dag([result.gradient_nodes_opt["y"]], inputs={"x": 2, "y": 3})
    log = next(n for n in dag["nodes"] if n["op"] == "Log")
    assert log["evaluatedValue"] == pytest.approx(math.log(2))
    assert "ln(2)" in log["calculation"]
    guide = explain_gradients(result.graph, {"x": 2, "y": 3})["y"]
    assert "ln(u)" in guide["steps"][0]["rule"]


def test_api_values_and_guides_change_with_program_and_inputs():
    client = TestClient(app)
    for source, inputs, expected in [
        ("fn f(x):\n    return x * x\n", {"x": 3}, 6),
        ("fn f(x):\n    return x * x\n", {"x": 4}, 8),
        ("fn f(x):\n    return x ^ 3\n", {"x": 4}, 48),
    ]:
        data = client.post("/api/compile", json={"source": source, "inputs": inputs}).json()
        assert data["success"]
        for dag in [data["dags"]["forwardRaw"], data["dags"]["forwardOpt"], data["dags"]["combined"], *data["dags"]["derivatives"].values()]:
            assert all(node["evaluatedValue"] is not None for node in dag["nodes"])
        derivative = data["dags"]["derivatives"]["x"]
        root = next(n for n in derivative["nodes"] if n["isRoot"])
        assert root["evaluatedValue"] == expected == data["gradients"]["x"]
        assert derivative["gradientExplanation"]["value"] == expected


def test_combined_root_roles_survive_shared_derivative_roots():
    data = TestClient(app).post("/api/compile", json={"source": "fn f(x, y):\n    return x + y\n"}).json()
    roots = [n for n in data["dags"]["combined"]["nodes"] if n["isRoot"]]
    assert any("d/dx" in n["rootNames"] and "d/dy" in n["rootNames"] for n in roots)


def test_negative_power_base_is_parenthesized_in_explanation():
    result = compile_source("fn f(x):\n    return x ^ 2\n", {"x": -3})
    dag = serialize_dag([result.output_opt], inputs={"x": -3})
    assert dag["nodes"][-1]["calculation"] == "(-3) ^ 2 = 9"
