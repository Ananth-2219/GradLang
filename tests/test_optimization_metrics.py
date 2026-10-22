"""Optimization reporting must compare like-for-like graph scopes."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from gradlang.codegen import generate_code, load_functions
from gradlang.compiler import compile_source
from gradlang.ir_graph import topological_sort


LOSS = "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n"
CASES = [
    (LOSS, {"x": 2.0, "w": 0.5, "b": 1.0}),
    ("fn f(x):\n    return x + (2 * 3)\n", {"x": 4.0}),
    ("fn f(x):\n    return x\n", {"x": 3.0}),
    ("fn f(x, y):\n    return (x * y) ^ 2\n", {"x": 2.0, "y": 3.0}),
]


@pytest.mark.parametrize("source,inputs", CASES)
def test_compiler_counts_match_forward_listings_and_unique_combined_nodes(source, inputs):
    result = compile_source(source, inputs)
    assert result.forward_nodes_before == len(result.ir_before.splitlines())
    assert result.forward_nodes_after == len(result.ir_after.splitlines())
    for forward, derivatives, count in [
        (result.graph.output, result.gradient_nodes, result.combined_nodes_before),
        (result.output_opt, result.gradient_nodes_opt, result.combined_nodes_after),
    ]:
        roots = [forward, *derivatives.values()]
        # Independent union demonstrates that shared nodes are counted once.
        unique_nodes = set().union(*(set(topological_sort([root])) for root in roots))
        assert count == len(unique_nodes) == len(topological_sort(roots))
    # Existing public fields retain their combined meaning.
    assert result.nodes_before == result.combined_nodes_before
    assert result.nodes_after == result.combined_nodes_after


@pytest.mark.parametrize("source,inputs", CASES)
def test_api_scoped_metrics_match_dags_and_preserve_legacy_fields(source, inputs):
    response = TestClient(app).post("/api/compile", json={"source": source, "inputs": inputs})
    assert response.status_code == 200
    data = response.json()
    assert data["success"]
    ir = data["ir"]
    forward, combined = ir["forward"], ir["combined"]
    assert forward["nodesBefore"] == len(ir["before"].splitlines())
    assert forward["nodesAfter"] == len(ir["after"].splitlines())
    assert forward["nodesBefore"] == len(data["dags"]["forwardRaw"]["nodes"])
    assert forward["nodesAfter"] == len(data["dags"]["forwardOpt"]["nodes"])
    assert combined["nodesAfter"] == len(data["dags"]["combined"]["nodes"])
    for metrics in (forward, combined):
        reduction = metrics["nodesBefore"] - metrics["nodesAfter"]
        assert metrics["nodeReduction"] == reduction
        assert metrics["percentReduction"] == round(reduction / metrics["nodesBefore"] * 100, 1)
    for key in ("nodesBefore", "nodesAfter", "nodeReduction", "percentReduction"):
        assert ir[key] == combined[key]


def test_loss_reduction_occurs_outside_unchanged_forward_ir():
    result = compile_source(LOSS)
    assert result.ir_before == result.ir_after
    assert (result.forward_nodes_before, result.forward_nodes_after) == (9, 9)
    assert (result.combined_nodes_before, result.combined_nodes_after) == (16, 14)
    roots = [result.output_opt, *result.gradient_nodes_opt.values()]
    assert sum(len(topological_sort([root])) for root in roots) > result.combined_nodes_after
    ir = TestClient(app).post("/api/compile", json={"source": LOSS}).json()["ir"]
    assert ir["forward"]["percentReduction"] == 0.0
    assert ir["combined"]["percentReduction"] == 12.5


def test_no_possible_optimization_reports_zero_for_both_scopes():
    ir = TestClient(app).post("/api/compile", json={
        "source": "fn f(x):\n    return x\n",
    }).json()["ir"]
    for scope in ("forward", "combined"):
        assert ir[scope]["nodesBefore"] == ir[scope]["nodesAfter"]
        assert ir[scope]["nodeReduction"] == 0
        assert ir[scope]["percentReduction"] == 0.0


@pytest.mark.parametrize("source,inputs", CASES)
def test_optimized_results_and_gradients_match_raw_graphs(source, inputs):
    result = compile_source(source, inputs)
    forward_src, gradient_src = generate_code(
        result.graph.name, result.parameters, result.graph.output, result.gradient_nodes
    )
    raw_forward, raw_gradient = load_functions(result.graph.name, forward_src, gradient_src)
    assert result.output == pytest.approx(raw_forward(**inputs))
    assert result.gradients == pytest.approx(raw_gradient(**inputs))
