"""Run the full scalar compiler and independently check two derivatives."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gradlang.lexer import tokenize
from gradlang.parser import Parser
from gradlang.semantic_analysis import analyze, SemanticError
from gradlang.ir_graph import build_graph, format_graph, topological_sort
from gradlang.autodiff import differentiate
from gradlang.optimizer import optimize
from gradlang.codegen import generate_code, load_functions


SAMPLE = """fn loss(x, w, b):
    y = w * x + b
    return (y - 1) ^ 2
"""
3

def compile_source(source):
    """Keep each compiler pass visible rather than hiding the pipeline."""
    function = Parser(tokenize(source)).parse()[0]
    analyze(function)
    graph = build_graph(function)
    gradients = differentiate(graph)
    roots = optimize([graph.output] + list(gradients.values()))
    gradients = dict(zip(gradients, roots[1:]))
    sources = generate_code(graph.name, graph.parameters, roots[0], gradients)
    return sources, load_functions(graph.name, *sources)


def main():
    sources, (forward, backward) = compile_source(SAMPLE)
    print("Generated Python:\n" + "\n".join(sources))
    values = {"x": 2.0, "w": 0.5, "b": 1.0}
    analytical = backward(**values)
    print("Forward:", forward(**values))
    print("Gradients:", analytical)
    epsilon = 1e-6
    for name in ("w", "b"):
        plus, minus = dict(values), dict(values)
        plus[name] += epsilon
        minus[name] -= epsilon
        numerical = (forward(**plus) - forward(**minus)) / (2 * epsilon)
        assert abs(analytical[name] - numerical) < 1e-5
        print(f"{name}: analytical={analytical[name]}, numerical={numerical:.9f}")

    shared = Parser(tokenize("fn shared(w, x):\n    return w*x + w*x\n")).parse()[0]
    # Normal construction already shares. Disable it solely to demonstrate CSE.
    raw = build_graph(shared, share=False)
    optimized = optimize([raw.output])[0]
    normal = build_graph(shared)
    before = len(topological_sort([raw.output]))
    after = len(topological_sort([optimized]))
    print(f"\nBefore CSE ({before} nodes; construction sharing disabled):")
    print(format_graph([raw.output]))
    print(f"After CSE ({after} nodes):")
    print(format_graph([optimized]))
    assert (before, after) == (5, 4)
    assert len(topological_sort([normal.output])) == after
    print("Default structural hashing also produces 4 nodes.")

    invalid = "fn invalid(x):\n    return x + missing\n"
    try:
        analyze(Parser(tokenize(invalid)).parse()[0])
    except SemanticError as error:
        print("\nExpected semantic error:", error)
    else:
        raise AssertionError("Undeclared variable was accepted")


if __name__ == "__main__":
    main()
