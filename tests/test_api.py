"""Tests for the GradLang FastAPI backend."""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_examples():
    response = client.get("/api/examples")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    ids = [ex["id"] for ex in data]
    assert "loss_linear" in ids
    assert "cse_demo" in ids


def test_compile_valid_code():
    req = {
        "source": "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n",
        "inputs": {"x": 2.0, "w": 0.5, "b": 0.0},
        "validate_gradients": True,
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["parameters"] == ["x", "w", "b"]
    assert len(data["tokens"]) > 0
    assert data["ast"]["type"] == "FunctionDef"
    assert "x" in data["symbols"]
    assert "w" in data["symbols"]
    assert "b" in data["symbols"]
    assert data["ir"]["nodesBefore"] > 0
    assert data["ir"]["nodesAfter"] > 0
    assert data["codegen"]["forwardSource"].startswith("def loss(")
    assert data["codegen"]["gradientSource"].startswith("def grad_loss(")
    assert data["execution"]["output"] == 0.0  # (0.5 * 2.0 + 0.0 - 1)^2 = 0
    assert "w" in data["execution"]["gradients"]
    assert "b" in data["execution"]["gradients"]
    assert "x" in data["execution"]["gradients"]
    # Check DAGs
    assert "forwardRaw" in data["dags"]
    assert "forwardOpt" in data["dags"]
    assert "combined" in data["dags"]
    assert "derivatives" in data["dags"]
    assert len(data["dags"]["combined"]["nodes"]) > 0
    # Check finite differences
    assert "w" in data["execution"]["finiteDifferences"]
    assert data["execution"]["finiteDifferences"]["w"]["status"] == "PASS"


def test_compile_cse_optimization():
    req = {
        "source": "fn f(x, y):\n    return x * y + x * y\n",
        "inputs": {"x": 3.0, "y": 4.0},
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Pre-opt vs post-opt nodes reduction
    assert data["ir"]["nodesBefore"] > data["ir"]["nodesAfter"]
    assert data["ir"]["nodeReduction"] > 0
    assert data["execution"]["output"] == 24.0


def test_compile_syntax_error():
    req = {
        "source": "fn bad(x\n    return x + 1\n",
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["phase"] == "Parser"
    assert data["errorType"] == "ParseError"


def test_compile_semantic_error():
    req = {
        "source": "fn f(x):\n    return x + y\n",
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["phase"] == "SemanticAnalysis"
    assert data["errorType"] == "SemanticError"


def test_compile_division_by_zero():
    req = {
        "source": "fn f(x, y):\n    return x / y\n",
        "inputs": {"x": 1.0, "y": 0.0},
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["errorType"] == "ZeroDivisionError"


def test_benchmark_endpoint():
    req = {
        "source": "fn loss(x, w, b):\n    return (w * x + b - 1) ^ 2\n",
        "inputs": {"x": 2.0, "w": 0.5, "b": 0.0},
        "iterations": 10,
    }
    response = client.post("/api/benchmark", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["iterations"] == 10
    assert "lexer" in data["phases"]
    assert "parser" in data["phases"]
    assert "semantic" in data["phases"]
    assert "ir_graph" in data["phases"]
    assert "autodiff" in data["phases"]
    assert "optimizer" in data["phases"]
    assert "codegen" in data["phases"]
    assert "execution" in data["phases"]
    assert data["total_compile_mean_us"] > 0


def test_verification_case_loss_function():
    """Required verification case:
    fn loss(x, w, b):
        y = w * x + b
        return (y - 1) ^ 2
    Inputs: x=2, w=0.5, b=1
    Expected: forward=1.0, d/dx=1.0, d/dw=4.0, d/db=2.0
    """
    req = {
        "source": "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n",
        "inputs": {"x": 2.0, "w": 0.5, "b": 1.0},
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["parameters"] == ["x", "w", "b"]

    # Both top-level and nested execution fields must be populated
    assert data["output"] == 1.0
    assert data["execution"]["output"] == 1.0

    grads = data["gradients"]
    exec_grads = data["execution"]["gradients"]
    assert grads["x"] == pytest.approx(1.0)
    assert grads["w"] == pytest.approx(4.0)
    assert grads["b"] == pytest.approx(2.0)

    assert exec_grads["x"] == pytest.approx(1.0)
    assert exec_grads["w"] == pytest.approx(4.0)
    assert exec_grads["b"] == pytest.approx(2.0)

    # Symbolic gradients and node counts
    assert "x" in data["symbolicGradients"]
    assert "w" in data["symbolicGradients"]
    assert "b" in data["symbolicGradients"]
    assert data["gradientNodeCounts"]["x"] > 0
    assert data["gradientNodeCounts"]["w"] > 0
    assert data["gradientNodeCounts"]["b"] > 0


def test_multiple_parameters_nonempty_gradients():
    """Verify non-empty gradients across multiple parameters."""
    req = {
        "source": "fn poly(a, b, c, d):\n    return a * b + c * d\n",
        "inputs": {"a": 2.0, "b": 3.0, "c": 4.0, "d": 5.0},
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["output"] == pytest.approx(26.0)
    assert data["gradients"]["a"] == pytest.approx(3.0)
    assert data["gradients"]["b"] == pytest.approx(2.0)
    assert data["gradients"]["c"] == pytest.approx(5.0)
    assert data["gradients"]["d"] == pytest.approx(4.0)


def test_unused_parameters_zero_gradients():
    """Unused parameters should yield analytical gradient of exactly 0.0."""
    req = {
        "source": "fn f(x, y, z):\n    return x ^ 2\n",
        "inputs": {"x": 3.0, "y": 10.0, "z": -5.0},
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["output"] == pytest.approx(9.0)
    assert data["gradients"]["x"] == pytest.approx(6.0)
    assert data["gradients"]["y"] == pytest.approx(0.0)
    assert data["gradients"]["z"] == pytest.approx(0.0)


def test_input_sanitization_extra_keys_and_strings():
    """API should gracefully handle extra keys, string numbers, and missing keys."""
    # Extra keys and string floats
    req = {
        "source": "fn f(x, y):\n    return x + y\n",
        "inputs": {"x": "2.5", "y": "3.5", "extraneous": 999.0},
    }
    response = client.post("/api/compile", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["output"] == pytest.approx(6.0)
    assert data["gradients"]["x"] == pytest.approx(1.0)
    assert data["gradients"]["y"] == pytest.approx(1.0)

    # Missing keys filled with defaults
    req2 = {
        "source": "fn f(x, y):\n    return x * y\n",
        "inputs": {"x": 4.0},  # y missing
    }
    response2 = client.post("/api/compile", json=req2)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["success"] is True
    # default y=1.0 -> 4.0 * 1.0 = 4.0
    assert data2["output"] == pytest.approx(4.0)
    assert data2["gradients"]["x"] == pytest.approx(1.0)
    assert data2["gradients"]["y"] == pytest.approx(4.0)

