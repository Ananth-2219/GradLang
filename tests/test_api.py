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
