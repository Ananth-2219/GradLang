"""Phase 3: comprehensive tests for the unified compiler pipeline.

Covers:
  - Valid programs (expressions, multiple variables, precedence, power, CSE)
  - Invalid programs (bad tokens, syntax, undefined vars, duplicates,
    indentation, calls, division by zero domain errors)
  - Automatic differentiation (every rule, chain rule, shared nodes,
    repeated variables, multi-input, zero/unused gradients)
  - Gradient correctness via central finite differences
  - Optimiser effectiveness (node count reductions, folding, CSE)
  - CompileResult structure and CLI helpers

All existing Phase 1 and Phase 2 tests continue to pass.
"""

import math
import unittest
from typing import Dict

# Phase 1 + 2 imports (unchanged)
from gradlang.lexer import tokenize, LexerError
from gradlang.parser import Parser, ParseError
from gradlang.ast_nodes import Assign, BinOp, FunctionDef, Num, Return, UnaryOp, Var
from gradlang.symbol_table import Symbol, SemanticError, build_symbol_table
from gradlang.semantic_analysis import analyze
from gradlang.ir_graph import build_graph, GraphBuilder, format_graph, topological_sort
from gradlang.autodiff import differentiate
from gradlang.optimizer import optimize
from gradlang.codegen import generate_code, load_functions

# Phase 3: unified pipeline
from gradlang.compiler import compile_source, CompileResult, _validate_inputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ast(source: str) -> FunctionDef:
    return Parser(tokenize(source)).parse()[0]


def quick_compile(expression: str, params: str = "x,y"):
    """Compile a one-expression function and return (forward_fn, grad_fn)."""
    src = f"fn f({params}):\n    return {expression}\n"
    result = compile_source(src)
    ns = {}
    exec(result.forward_source + "\n" + result.gradient_source, ns)
    return ns["f"], ns["grad_f"]


def numerical_gradient(forward_fn, inputs: Dict[str, float],
                        name: str, eps: float = 1e-6) -> float:
    """Central finite difference for one parameter."""
    plus, minus = dict(inputs), dict(inputs)
    plus[name] += eps
    minus[name] -= eps
    return (forward_fn(**plus) - forward_fn(**minus)) / (2 * eps)


def check_gradients(test_case, expression: str, inputs: Dict[str, float],
                    params: str = None, tol: float = 1e-5):
    """Assert analytical ≈ numerical for each parameter."""
    if params is None:
        params = ",".join(inputs)
    fwd, bwd = quick_compile(expression, params)
    analytical = bwd(**inputs)
    for name in inputs:
        num = numerical_gradient(fwd, inputs, name)
        test_case.assertAlmostEqual(
            analytical[name], num, delta=tol,
            msg=f"Gradient of {expression!r} w.r.t. {name!r} at {inputs}: "
                f"analytical={analytical[name]}, numerical={num}"
        )


# ===========================================================================
# 1. Valid programs
# ===========================================================================

class TestValidPrograms(unittest.TestCase):

    def test_simple_number_constant(self):
        result = compile_source("fn f():\n    return 42\n", inputs={})
        self.assertEqual(result.output, 42)
        self.assertEqual(result.gradients, {})

    def test_single_variable(self):
        result = compile_source("fn f(x):\n    return x\n", inputs={"x": 5.0})
        self.assertEqual(result.output, 5.0)
        self.assertAlmostEqual(result.gradients["x"], 1.0)

    def test_addition(self):
        result = compile_source("fn f(x, y):\n    return x + y\n",
                                inputs={"x": 3.0, "y": 4.0})
        self.assertEqual(result.output, 7.0)

    def test_subtraction(self):
        result = compile_source("fn f(x, y):\n    return x - y\n",
                                inputs={"x": 10.0, "y": 3.5})
        self.assertAlmostEqual(result.output, 6.5)

    def test_multiplication(self):
        result = compile_source("fn f(x, y):\n    return x * y\n",
                                inputs={"x": 3.0, "y": 4.0})
        self.assertEqual(result.output, 12.0)

    def test_division(self):
        result = compile_source("fn f(x, y):\n    return x / y\n",
                                inputs={"x": 7.0, "y": 2.0})
        self.assertAlmostEqual(result.output, 3.5)

    def test_nested_parentheses(self):
        # ((3 + 4) * (2 - 1)) = 7
        result = compile_source(
            "fn f():\n    return ((3 + 4) * (2 - 1))\n", inputs={})
        self.assertEqual(result.output, 7)

    def test_operator_precedence_mul_over_add(self):
        # 2 + 3 * 4 = 14 (not 20)
        result = compile_source("fn f():\n    return 2 + 3 * 4\n", inputs={})
        self.assertEqual(result.output, 14)

    def test_operator_precedence_div_before_sub(self):
        # 10 - 6 / 2 = 7 (not 2)
        result = compile_source("fn f():\n    return 10 - 6 / 2\n", inputs={})
        self.assertEqual(result.output, 7.0)

    def test_left_associativity_subtraction(self):
        # 8 - 3 - 1 = 4 (not 6)
        result = compile_source("fn f():\n    return 8 - 3 - 1\n", inputs={})
        self.assertEqual(result.output, 4)

    def test_left_associativity_division(self):
        # 8 / 2 / 2 = 2 (not 8)
        result = compile_source("fn f():\n    return 8 / 2 / 2\n", inputs={})
        self.assertEqual(result.output, 2.0)

    def test_right_associativity_power(self):
        # 2^3^2 = 2^9 = 512 (not 64)
        result = compile_source("fn f():\n    return 2^3^2\n", inputs={})
        self.assertEqual(result.output, 512)

    def test_exponentiation_basic(self):
        result = compile_source("fn f(x):\n    return x^3\n", inputs={"x": 2.0})
        self.assertEqual(result.output, 8.0)

    def test_unary_minus(self):
        result = compile_source("fn f(x):\n    return -x\n", inputs={"x": 5.0})
        self.assertEqual(result.output, -5.0)

    def test_unary_minus_precedence_over_power(self):
        # -2^2 = -(2^2) = -4  (not (-2)^2 = 4)
        result = compile_source("fn f():\n    return -2^2\n", inputs={})
        self.assertEqual(result.output, -4)

    def test_multiple_assignments(self):
        src = ("fn f(x, w, b):\n"
               "    y = w * x + b\n"
               "    return (y - 1) ^ 2\n")
        result = compile_source(src, inputs={"x": 2.0, "w": 0.5, "b": 1.0})
        self.assertEqual(result.output, 1.0)
        self.assertAlmostEqual(result.gradients["x"], 1.0)
        self.assertAlmostEqual(result.gradients["w"], 4.0)
        self.assertAlmostEqual(result.gradients["b"], 2.0)

    def test_repeated_subexpression_value(self):
        # w*x + w*x = 2*w*x
        result = compile_source("fn f(w, x):\n    return w*x + w*x\n",
                                inputs={"w": 3.0, "x": 4.0})
        self.assertEqual(result.output, 24.0)

    def test_complex_expression(self):
        # (x*y + 1)^2 at x=2, y=3: (7)^2 = 49
        result = compile_source("fn f(x, y):\n    return (x*y + 1)^2\n",
                                inputs={"x": 2.0, "y": 3.0})
        self.assertEqual(result.output, 49.0)

    def test_reassignment(self):
        src = "fn f(x, y):\n    x = x * x\n    return x + x\n"
        result = compile_source(src, inputs={"x": 3.0, "y": 7.0})
        self.assertEqual(result.output, 18.0)

    def test_float_literals(self):
        result = compile_source("fn f():\n    return .5 + 1.5e1\n", inputs={})
        self.assertAlmostEqual(result.output, 15.5)

    def test_zero_parameter_function(self):
        result = compile_source("fn f():\n    return 5\n", inputs={})
        self.assertEqual(result.output, 5)
        self.assertEqual(result.gradients, {})

    def test_multiple_functions_first_is_compiled(self):
        src = ("fn f(x):\n    return x\n"
               "fn g(x):\n    return x * 2\n")
        result = compile_source(src, inputs={"x": 3.0})
        # Only the first function is compiled through the full pipeline
        self.assertEqual(result.ast.name, "f")
        self.assertEqual(result.output, 3.0)


# ===========================================================================
# 2. Invalid programs
# ===========================================================================

class TestInvalidPrograms(unittest.TestCase):

    def test_illegal_character(self):
        with self.assertRaises(LexerError):
            compile_source("fn f(x):\n    return x @ 2\n")

    def test_tab_character(self):
        with self.assertRaises(LexerError):
            compile_source("fn f(x):\n\treturn x\n")

    def test_missing_return(self):
        with self.assertRaises(ParseError):
            compile_source("fn f(x):\n    x = 1\n")

    def test_missing_colon(self):
        with self.assertRaises(ParseError):
            compile_source("fn f(x)\n    return x\n")

    def test_unmatched_parenthesis(self):
        with self.assertRaises(ParseError):
            compile_source("fn f(x):\n    return (x + 1\n")

    def test_trailing_comma_in_params(self):
        with self.assertRaises(ParseError):
            compile_source("fn f(x,):\n    return x\n")

    def test_empty_source(self):
        with self.assertRaises(ParseError):
            compile_source("")

    def test_undefined_identifier(self):
        with self.assertRaises(SemanticError):
            compile_source("fn f(x):\n    return x + missing\n")

    def test_use_before_definition(self):
        with self.assertRaises(SemanticError):
            compile_source("fn f(x):\n    y = z + x\n    z = 1\n    return y\n")

    def test_self_referencing_assignment(self):
        with self.assertRaises(SemanticError):
            compile_source("fn f():\n    x = x + 1\n    return x\n")

    def test_duplicate_parameter(self):
        with self.assertRaises(SemanticError):
            compile_source("fn f(x, x):\n    return x\n")

    def test_inconsistent_indentation(self):
        with self.assertRaises(LexerError):
            compile_source("fn f(x):\n    x = 1\n  return x\n")

    def test_function_call_rejected_by_semantic(self):
        with self.assertRaises(SemanticError):
            compile_source("fn f(x):\n    return sin(x)\n")

    def test_incompatible_vector_shapes(self):
        fn = ast("fn f(x,y):\n    z = x + y\n    return z\n")
        v3 = Symbol("vector", (3,))
        v4 = Symbol("vector", (4,))
        with self.assertRaisesRegex(SemanticError, "Incompatible shapes"):
            analyze(fn, {"x": v3, "y": v4})

    def test_vector_lowering_rejected(self):
        fn = ast("fn f(x, y):\n    return x + y\n")
        v = Symbol("vector", (3,))
        with self.assertRaisesRegex(ValueError, "scalars only"):
            build_graph(fn, {"x": v})

    def test_keyword_function_name_rejected(self):
        with self.assertRaisesRegex(ValueError, "Python identifier"):
            compile_source("fn class(x):\n    return x\n")

    def test_validate_inputs_missing(self):
        with self.assertRaisesRegex(ValueError, "Missing input"):
            _validate_inputs({"x": 1.0}, ["x", "y"])

    def test_validate_inputs_extra(self):
        with self.assertRaisesRegex(ValueError, "Unexpected input"):
            _validate_inputs({"x": 1.0, "z": 2.0}, ["x"])

    def test_validate_inputs_non_numeric(self):
        with self.assertRaisesRegex(TypeError, "must be a number"):
            _validate_inputs({"x": "hello"}, ["x"])

    def test_division_by_zero_at_runtime(self):
        result = compile_source("fn f(x, y):\n    return x / y\n")
        ns = {}
        exec(result.forward_source, ns)
        with self.assertRaises((ZeroDivisionError, ValueError)):
            ns["f"](1.0, 0.0)

    def test_log_of_negative_base_at_runtime(self):
        """d/dy of x^y requires log(x); for x<0 this is a domain error."""
        result = compile_source("fn f(x, y):\n    return x^y\n")
        ns = {}
        exec(result.forward_source + "\n" + result.gradient_source, ns)
        # Python's math.log raises ValueError for negative arguments;
        # the gradient w.r.t. y is undefined at x=-2.
        with self.assertRaises((ValueError, ZeroDivisionError)):
            ns["grad_f"](-2.0, 3.0)

    def test_unary_plus_unsupported(self):
        with self.assertRaises(ParseError):
            compile_source("fn f(x):\n    return +x\n")


# ===========================================================================
# 3. Automatic differentiation
# ===========================================================================

class TestAutodiff(unittest.TestCase):

    def test_addition_gradients(self):
        # d/dx (x+y)=1, d/dy (x+y)=1
        check_gradients(self, "x+y", {"x": 2.0, "y": 3.0})

    def test_subtraction_gradients(self):
        # d/dx (x-y)=1, d/dy (x-y)=-1
        check_gradients(self, "x-y", {"x": 5.0, "y": 2.0})

    def test_multiplication_gradients(self):
        # d/dx (x*y)=y, d/dy (x*y)=x
        check_gradients(self, "x*y", {"x": 3.0, "y": 4.0})

    def test_division_gradient_dx(self):
        # d/dx (x/y) = 1/y
        check_gradients(self, "x/y", {"x": 6.0, "y": 3.0})

    def test_division_gradient_dy(self):
        # d/dy (x/y) = -x/y^2
        check_gradients(self, "x/y", {"x": 6.0, "y": 2.0})

    def test_power_constant_exponent(self):
        # d/dx (x^3) = 3*x^2
        fwd, bwd = quick_compile("x^3", "x")
        self.assertAlmostEqual(bwd(x=2.0)["x"], 12.0)
        self.assertAlmostEqual(bwd(x=3.0)["x"], 27.0)

    def test_power_zero_exponent(self):
        # d/dx (x^0) = 0 always (special case)
        _, bwd = quick_compile("x^0", "x")
        self.assertEqual(bwd(x=0.0)["x"], 0)
        self.assertEqual(bwd(x=5.0)["x"], 0)

    def test_power_one_exponent(self):
        # d/dx (x^1) = 1
        _, bwd = quick_compile("x^1", "x")
        self.assertAlmostEqual(bwd(x=3.0)["x"], 1.0)

    def test_power_variable_exponent(self):
        # d/dx (x^y) = y * x^(y-1), d/dy = x^y * log(x)
        check_gradients(self, "x^y", {"x": 2.0, "y": 3.0})

    def test_chain_rule_nested(self):
        # d/dx ((x*y+1)^2) = 2*(x*y+1)*y
        check_gradients(self, "(x*y+1)^2", {"x": 1.7, "y": 2.3})

    def test_shared_computation_node(self):
        # t = w*x; output = t+t => d/dw = 2*x, d/dx = 2*w
        fwd, bwd = quick_compile("w*x + w*x", "w,x")
        g = bwd(w=3.0, x=4.0)
        self.assertAlmostEqual(g["w"], 8.0)   # 2 * x
        self.assertAlmostEqual(g["x"], 6.0)   # 2 * w

    def test_repeated_variable_usage(self):
        # x*x => d/dx = 2*x
        check_gradients(self, "x*x", {"x": 3.0}, "x")

    def test_multiple_input_variables(self):
        check_gradients(self, "x*x+x*x", {"x": 1.7, "y": 2.3})

    def test_zero_gradient_unused_variable(self):
        fwd, bwd = quick_compile("x", "x,y")
        g = bwd(x=5.0, y=7.0)
        self.assertAlmostEqual(g["x"], 1.0)
        self.assertAlmostEqual(g["y"], 0.0)

    def test_unary_minus_gradient(self):
        # d/dx (-x) = -1
        check_gradients(self, "-x", {"x": 4.0}, "x")

    def test_double_unary_minus(self):
        # d/dx (--x) = 1
        check_gradients(self, "--x", {"x": 3.0}, "x")

    def test_gradient_with_intermediate_assignment(self):
        # fn f(x,w,b): y=w*x+b; return (y-1)^2
        src = "fn f(x,w,b):\n    y = w*x+b\n    return (y-1)^2\n"
        result = compile_source(src, inputs={"x": 2.0, "w": 0.5, "b": 1.0})
        self.assertAlmostEqual(result.gradients["x"], 1.0)
        self.assertAlmostEqual(result.gradients["w"], 4.0)
        self.assertAlmostEqual(result.gradients["b"], 2.0)

    def test_gradient_reassignment(self):
        # fn f(x,y): x=x*x; return x+x  => out=2*(x_in^2) => d/dx=4*x_in
        src = "fn f(x,y):\n    x = x*x\n    return x+x\n"
        result = compile_source(src, inputs={"x": 3.0, "y": 7.0})
        self.assertAlmostEqual(result.gradients["x"], 12.0)  # 4*3
        self.assertAlmostEqual(result.gradients["y"], 0.0)

    def test_all_rules_finite_differences(self):
        """Sweep every operator against numerical gradients at generic points."""
        cases = [
            ("x+y", {"x": 1.7, "y": 2.3}),
            ("x-y", {"x": 1.7, "y": 2.3}),
            ("x*y", {"x": 1.7, "y": 2.3}),
            ("x/y", {"x": 1.7, "y": 2.3}),
            ("x^3", {"x": 1.7, "y": 2.3}),
            ("x^y", {"x": 1.7, "y": 2.3}),
            ("-x", {"x": 1.7, "y": 2.3}),
            ("x*x+x*x", {"x": 1.7, "y": 2.3}),
            ("(x*y+1)^2", {"x": 1.7, "y": 2.3}),
        ]
        for expr, inp in cases:
            with self.subTest(expr=expr):
                check_gradients(self, expr, inp)

    def test_gradient_correctness_power_symbolic(self):
        """Check power rule for several constant exponents analytically."""
        for n, x_val in [(2, 3.0), (3, 2.0), (4, 1.5)]:
            _, bwd = quick_compile(f"x^{n}", "x")
            expected = n * (x_val ** (n - 1))
            self.assertAlmostEqual(bwd(x=x_val)["x"], expected, places=8,
                                   msg=f"x^{n} at x={x_val}")


# ===========================================================================
# 4. Optimiser effectiveness
# ===========================================================================

class TestOptimiser(unittest.TestCase):

    def test_constant_folding_simple(self):
        builder = GraphBuilder()
        node = builder.node("Add", builder.const(2), builder.const(3))
        [folded] = optimize([node])
        self.assertEqual(folded.op, "Const")
        self.assertEqual(folded.value, 5)

    def test_constant_folding_chain(self):
        builder = GraphBuilder()
        a = builder.const(2)
        b = builder.const(3)
        c = builder.const(4)
        product = builder.node("Mul", a, builder.node("Add", b, c))
        [folded] = optimize([product])
        self.assertEqual(folded.op, "Const")
        self.assertEqual(folded.value, 14)

    def test_constant_folding_power(self):
        builder = GraphBuilder()
        node = builder.node("Pow", builder.const(2), builder.const(10))
        [folded] = optimize([node])
        self.assertEqual(folded.op, "Const")
        self.assertEqual(folded.value, 1024)

    def test_cse_duplicate_multiply(self):
        fn = ast("fn f(w, x):\n    return w*x + w*x\n")
        raw = build_graph(fn, share=False)
        before = len(topological_sort([raw.output]))
        [opt] = optimize([raw.output])
        after = len(topological_sort([opt]))
        self.assertEqual(before, 5)
        self.assertEqual(after, 4)
        self.assertIs(opt.inputs[0], opt.inputs[1])

    def test_cse_exposes_parent_duplicate(self):
        """Folding constants can expose a previously distinct parent as a duplicate."""
        builder = GraphBuilder()
        x = builder.node("Var", value="x")
        s1 = builder.node("Add", builder.const(2), builder.const(3))   # -> 5
        s2 = builder.const(5)
        m1 = builder.node("Mul", x, s1)
        m2 = builder.node("Mul", x, s2)
        roots = optimize([m1, m2])
        self.assertIs(roots[0], roots[1])

    def test_invalid_constant_retained(self):
        """Divide-by-zero constant operations must NOT be folded."""
        builder = GraphBuilder()
        node = builder.node("Div", builder.const(1), builder.const(0))
        [result] = optimize([node])
        self.assertEqual(result.op, "Div")   # Not folded

    def test_default_sharing_equals_cse_result(self):
        fn = ast("fn f(w, x):\n    return w*x + w*x\n")
        shared = build_graph(fn)   # sharing=True by default
        raw = build_graph(fn, share=False)
        [opt] = optimize([raw.output])
        self.assertEqual(len(topological_sort([shared.output])),
                         len(topological_sort([opt])))

    def test_node_counts_reported_in_result(self):
        src = "fn f(w, x):\n    return w*x + w*x\n"
        result = compile_source(src)
        # nodes_before counts forward + gradient roots together; just check
        # optimiser does not increase the count
        self.assertGreaterEqual(result.nodes_before, result.nodes_after)

    def test_optimised_output_matches_unoptimised(self):
        """Optimisation must not change numerical results."""
        expressions = ["x+y", "x*y-1", "(x+y)^2", "x^3/y"]
        vals = {"x": 2.5, "y": 1.5}
        for expr in expressions:
            with self.subTest(expr=expr):
                src = f"fn f(x,y):\n    return {expr}\n"
                result = compile_source(src, inputs=vals)
                # Cross-check with direct Python eval
                x, y = vals["x"], vals["y"]
                expected = eval(expr.replace("^", "**"))
                self.assertAlmostEqual(result.output, expected, places=10)


# ===========================================================================
# 5. CompileResult structure
# ===========================================================================

class TestCompileResult(unittest.TestCase):

    def setUp(self):
        src = "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n"
        self.result = compile_source(src, inputs={"x": 2.0, "w": 0.5, "b": 1.0})

    def test_tokens_present(self):
        self.assertGreater(len(self.result.tokens), 0)
        self.assertEqual(self.result.tokens[-1].kind, "EOF")

    def test_ast_correct_type(self):
        self.assertIsInstance(self.result.ast, FunctionDef)
        self.assertEqual(self.result.ast.name, "loss")

    def test_symbols_populated(self):
        self.assertIn("x", self.result.symbols)
        self.assertIn("y", self.result.symbols)
        self.assertIn("w", self.result.symbols)
        self.assertIn("b", self.result.symbols)

    def test_ir_before_and_after_are_strings(self):
        self.assertIsInstance(self.result.ir_before, str)
        self.assertIsInstance(self.result.ir_after, str)
        self.assertGreater(len(self.result.ir_before), 0)
        self.assertGreater(len(self.result.ir_after), 0)

    def test_generated_source_contains_def(self):
        self.assertIn("def loss(", self.result.forward_source)
        self.assertIn("def grad_loss(", self.result.gradient_source)

    def test_output_value(self):
        self.assertAlmostEqual(self.result.output, 1.0)

    def test_gradient_values(self):
        self.assertAlmostEqual(self.result.gradients["x"], 1.0)
        self.assertAlmostEqual(self.result.gradients["w"], 4.0)
        self.assertAlmostEqual(self.result.gradients["b"], 2.0)

    def test_parameters_list(self):
        self.assertEqual(self.result.parameters, ["x", "w", "b"])

    def test_no_exec_when_inputs_none(self):
        result = compile_source("fn f(x):\n    return x\n", inputs=None)
        self.assertIsNone(result.output)
        self.assertIsNone(result.gradients)

    def test_node_counts_non_negative(self):
        self.assertGreater(self.result.nodes_before, 0)
        self.assertGreater(self.result.nodes_after, 0)


# ===========================================================================
# 6. Regression: all Phase 1 and Phase 2 tests still pass
#    (re-imported here just to make the Phase 3 run catch any regressions)
# ===========================================================================

class TestPhase1Regression(unittest.TestCase):

    def test_sample_tree(self):
        from gradlang.ast_nodes import Assign, BinOp, FunctionDef, Num, Return, Var
        source = "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n"
        expected = FunctionDef("loss", ["x", "w", "b"], [
            Assign("y", BinOp(BinOp(Var("w"), "*", Var("x")), "+", Var("b"))),
            Return(BinOp(BinOp(Var("y"), "-", Num(1)), "^", Num(2))),
        ])
        self.assertEqual(Parser(tokenize(source)).parse(), [expected])

    def test_precedence_cases(self):
        def pe(expr):
            return Parser(tokenize(f"fn f():\n    return {expr}\n")).parse()[0].body[0].value
        self.assertEqual(pe("2+3*4"), BinOp(Num(2), "+", BinOp(Num(3), "*", Num(4))))
        self.assertEqual(pe("8-3-1"), BinOp(BinOp(Num(8), "-", Num(3)), "-", Num(1)))
        self.assertEqual(pe("2^3^4"), BinOp(Num(2), "^", BinOp(Num(3), "^", Num(4))))


class TestPhase2Regression(unittest.TestCase):

    def test_codegen_sample(self):
        src = "fn loss(x,w,b):\n    y = w*x+b\n    return (y-1)^2\n"
        result = compile_source(src, inputs={"x": 2.0, "w": 0.5, "b": 1.0})
        self.assertAlmostEqual(result.output, 1.0)
        self.assertAlmostEqual(result.gradients["x"], 1.0)
        self.assertAlmostEqual(result.gradients["w"], 4.0)
        self.assertAlmostEqual(result.gradients["b"], 2.0)

    def test_cse_correctness(self):
        fn = ast("fn f(w,x):\n    return w*x + w*x\n")
        raw = build_graph(fn, share=False)
        [opt] = optimize([raw.output])
        self.assertIs(opt.inputs[0], opt.inputs[1])

    def test_finite_differences_regression(self):
        for expr in ("x+y", "x-y", "x*y", "x/y", "x^3", "x^y", "-x",
                     "x*x+x*x", "(x*y+1)^2"):
            with self.subTest(expr=expr):
                check_gradients(self, expr, {"x": 1.7, "y": 2.3})


if __name__ == "__main__":
    unittest.main(verbosity=2)
