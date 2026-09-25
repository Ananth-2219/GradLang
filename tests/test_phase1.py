"""Behavioral checks for tree shape, layout, and positioned diagnostics."""

import unittest

from gradlang.ast_nodes import Assign, BinOp, Call, FunctionDef, Num, Return, UnaryOp, Var
from gradlang.lexer import LexerError, tokenize
from gradlang.parser import ParseError, Parser


def parse_expression(expression):
    return Parser(tokenize(f"fn f():\n    return {expression}\n")).parse()[0].body[0].value


class Phase1Tests(unittest.TestCase):
    def test_sample_tree(self):
        source = "fn loss(x, w, b):\n    y = w * x + b\n    return (y - 1) ^ 2\n"
        expected = FunctionDef("loss", ["x", "w", "b"], [
            Assign("y", BinOp(BinOp(Var("w"), "*", Var("x")), "+", Var("b"))),
            Return(BinOp(BinOp(Var("y"), "-", Num(1)), "^", Num(2))),
        ])
        self.assertEqual(Parser(tokenize(source)).parse(), [expected])

    def test_precedence_and_associativity(self):
        cases = {
            "2+3*4": BinOp(Num(2), "+", BinOp(Num(3), "*", Num(4))),
            "8-3-1": BinOp(BinOp(Num(8), "-", Num(3)), "-", Num(1)),
            "8/2*3": BinOp(BinOp(Num(8), "/", Num(2)), "*", Num(3)),
            "2^3^4": BinOp(Num(2), "^", BinOp(Num(3), "^", Num(4))),
            "-2^2": UnaryOp("-", BinOp(Num(2), "^", Num(2))),
            "2^-3": BinOp(Num(2), "^", UnaryOp("-", Num(3))),
            "(-2)^2": BinOp(UnaryOp("-", Num(2)), "^", Num(2)),
            "--x": UnaryOp("-", UnaryOp("-", Var("x"))),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(parse_expression(source), expected)

    def test_calls_and_numbers(self):
        self.assertEqual(parse_expression("f(.5, g(), 2e-3)"),
                         Call("f", [Num(0.5), Call("g", []), Num(0.002)]))

    def test_layout_and_missing_final_newline(self):
        source = "\r\nfn f():\r\n  return 1\r\n  \r\nfn g(x):\r\n    return x"
        functions = Parser(tokenize(source)).parse()
        self.assertEqual([function.name for function in functions], ["f", "g"])
        kinds = [token.kind for token in tokenize(source)]
        self.assertEqual(kinds.count("INDENT"), 2)
        self.assertEqual(kinds.count("DEDENT"), 2)
        self.assertEqual(kinds[-1], "EOF")

    def test_keyword_boundaries_and_positions(self):
        tokens = tokenize("fn function(return_value):\n    return return_value")
        self.assertEqual((tokens[1].kind, tokens[1].value), ("IDENT", "function"))
        token = next(token for token in tokens if token.kind == "RETURN")
        self.assertEqual((token.line, token.column), (2, 5))

    def test_positioned_errors(self):
        with self.assertRaisesRegex(LexerError, r"Illegal character '@'.*line 2, column 14"):
            tokenize("fn f():\n    return x @ 2")
        with self.assertRaisesRegex(ParseError, r"line 2, column 17"):
            Parser(tokenize("fn f():\n    return (x + )")).parse()
        with self.assertRaisesRegex(LexerError, r"Tabs.*line 2, column 1"):
            tokenize("fn f():\n\treturn 1")
        with self.assertRaisesRegex(LexerError, r"indentation.*line 3, column 3"):
            tokenize("fn f():\n    x = 1\n  return x")

    def test_malformed_programs(self):
        sources = [
            "", "fn f():\nreturn 1", "fn f()\n    return 1",
            "fn f(x,):\n    return x", "fn f():\n    x = 1",
            "fn f():\n    return 1\n    x = 2", "fn f():\n    return f(1,)",
            "fn f():\n    return (1+2", "fn f():\n    return +1",
            "fn f():\n    return 1 2", "fn f():\n    return 1\nx = 2",
            "fn f():\n    x = 1\n        return x",
        ]
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ParseError, r"line \d+, column \d+"):
                    Parser(tokenize(source)).parse()


if __name__ == "__main__":
    unittest.main()
