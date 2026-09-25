"""Independent pass checks plus finite differences for every derivative rule."""

import unittest
from gradlang.lexer import tokenize
from gradlang.parser import Parser
from gradlang.symbol_table import build_symbol_table, Symbol, SemanticError
from gradlang.semantic_analysis import analyze
from gradlang.ir_graph import build_graph, GraphBuilder, topological_sort
from gradlang.autodiff import differentiate
from gradlang.optimizer import optimize
from gradlang.codegen import generate_code, load_functions


def ast(source):
    return Parser(tokenize(source)).parse()[0]


def compile_function(source):
    graph = build_graph(ast(source))
    gradients = differentiate(graph)
    roots = optimize([graph.output] + list(gradients.values()))
    sources = generate_code(graph.name, graph.parameters, roots[0], dict(zip(gradients, roots[1:])))
    return load_functions(graph.name, *sources)


class Phase2Tests(unittest.TestCase):
    def test_symbols_and_errors(self):
        table = build_symbol_table(ast("fn f(x):\n    y = x + 1\n    return y"))
        self.assertEqual(table, {"x": Symbol(), "y": Symbol()})
        for source, message in [
            ("fn f(x,x):\n    return x", "Duplicate parameter.*line 1"),
            ("fn f(x):\n    y = z + x\n    z = 1\n    return y", "'z'.*line 2"),
            ("fn f():\n    x = x + 1\n    return x", "'x'.*line 2"),
            ("fn f(x):\n    return sin(x)", "calls.*line 2"),
        ]:
            with self.subTest(source=source), self.assertRaisesRegex(SemanticError, message):
                analyze(ast(source))

    def test_shapes(self):
        function = ast("fn f(x,y):\n    z = x + y\n    return z")
        vector = Symbol("vector", (3,))
        self.assertEqual(analyze(function, {"x": vector})["z"], vector)
        self.assertEqual(analyze(function, {"x": vector, "y": vector})["z"], vector)
        with self.assertRaisesRegex(SemanticError, "Incompatible shapes.*x.*y.*line 2"):
            analyze(function, {"x": vector, "y": Symbol("vector", (4,))})
        with self.assertRaisesRegex(ValueError, "scalars only"):
            build_graph(function, {"x": vector})

    def test_cse_and_folding(self):
        function = ast("fn f(w,x):\n    return w*x + w*x")
        raw = build_graph(function, share=False)
        shared = build_graph(function)
        result = optimize([raw.output])[0]
        self.assertEqual(len(topological_sort([raw.output])), 5)
        self.assertEqual(len(topological_sort([result])), 4)
        self.assertIs(result.inputs[0], result.inputs[1])
        self.assertIs(shared.output.inputs[0], shared.output.inputs[1])
        builder = GraphBuilder()
        folded = optimize([builder.node("Add", builder.const(2), builder.const(3))])[0]
        self.assertEqual((folded.op, folded.value), ("Const", 5))
        # Folding children exposes a new duplicate parent (x*5).
        x = builder.node("Var", value="x")
        sum_node = builder.node("Add", builder.const(2), builder.const(3))
        first = builder.node("Mul", x, sum_node)
        second = builder.node("Mul", x, builder.const(5))
        roots = optimize([first, second])
        self.assertIs(roots[0], roots[1])

    def test_rules_against_finite_differences(self):
        for expression in ("x+y", "x-y", "x*y", "x/y", "x^3", "x^y", "-x",
                           "x*x+x*x", "(x*y+1)^2"):
            with self.subTest(expression=expression):
                forward, backward = compile_function(f"fn f(x,y):\n    return {expression}")
                values = {"x": 1.7, "y": 2.3}
                gradients = backward(**values)
                for name in values:
                    plus, minus = dict(values), dict(values)
                    plus[name] += 1e-6
                    minus[name] -= 1e-6
                    numerical = (forward(**plus) - forward(**minus)) / 2e-6
                    self.assertAlmostEqual(gradients[name], numerical, places=5)

    def test_reassignment_unused_inputs_and_zero_powers(self):
        forward, backward = compile_function("fn f(x,y):\n    x = x*x\n    return x+x")
        self.assertEqual(forward(3, 7), 18)
        self.assertEqual(backward(3, 7), {"x": 12, "y": 0})
        for exponent, expected in [(0, 0), (1, 1), (2, 0), ("(1-1)", 0)]:
            _, backward = compile_function(f"fn f(x):\n    return x^{exponent}")
            self.assertEqual(backward(0)["x"], expected)
        forward, backward = compile_function("fn f():\n    return 5")
        self.assertEqual((forward(), backward()), (5, {}))

    def test_codegen_names_and_sample(self):
        forward, backward = compile_function("fn loss(x,w,b):\n    y = w*x+b\n    return (y-1)^2")
        self.assertEqual(forward(2, .5, 1), 1)
        self.assertEqual(backward(2, .5, 1), {"x": 1, "w": 4, "b": 2})
        forward, backward = compile_function("fn f(_t0,_t1):\n    return _t0^_t1")
        self.assertEqual(forward(2, 3), 8)
        self.assertAlmostEqual(backward(2, 3)["_t0"], 12)
        with self.assertRaisesRegex(ValueError, "Python identifier"):
            compile_function("fn class(x):\n    return x")


if __name__ == "__main__":
    unittest.main()
