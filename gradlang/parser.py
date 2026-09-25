"""Recursive-descent parser: each expression method implements one grammar rule."""

from typing import List

from .ast_nodes import Assign, BinOp, Call, Expr, FunctionDef, Num, Return, UnaryOp, Var
from .lexer import Token


class ParseError(SyntaxError):
    """A token does not fit the GradLang grammar."""


class Parser:
    def __init__(self, tokens: List[Token]):
        if not tokens or tokens[-1].kind != "EOF":
            raise ValueError("Token stream must end with EOF")
        self.tokens = tokens
        self.position = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.position]

    def error(self, expected: str) -> ParseError:
        token = self.current
        found = repr(token.value) if token.value else token.kind
        return ParseError(
            f"Expected {expected}, found {found} at line {token.line}, column {token.column}"
        )

    def expect(self, kind: str) -> Token:
        if self.current.kind != kind:
            raise self.error(kind)
        token = self.current
        self.position += 1
        return token

    def parse(self) -> List[FunctionDef]:
        """A program contains at least one function and consumes the full stream."""
        functions = [self.function()]
        while self.current.kind != "EOF":
            functions.append(self.function())
        self.expect("EOF")
        return functions

    def function(self) -> FunctionDef:
        start = self.expect("FN")
        name = self.expect("IDENT").value
        self.expect("(")
        params = []
        if self.current.kind != ")":
            params.append(self.expect("IDENT").value)
            while self.current.kind == ",":
                self.expect(",")
                params.append(self.expect("IDENT").value)
        self.expect(")")
        self.expect(":")
        self.expect("NEWLINE")
        self.expect("INDENT")

        body = []
        while self.current.kind == "IDENT":
            target_token = self.expect("IDENT")
            target = target_token.value
            self.expect("=")
            body.append(Assign(target, self.expression(), line=target_token.line))
            self.expect("NEWLINE")
        return_token = self.expect("RETURN")
        body.append(Return(self.expression(), line=return_token.line))
        self.expect("NEWLINE")
        self.expect("DEDENT")
        return FunctionDef(name, params, body, line=start.line)

    def expression(self) -> Expr:
        return self.additive()

    def additive(self) -> Expr:
        node = self.multiplicative()
        # Updating the left subtree makes equal-precedence operators left-associative.
        while self.current.kind in ("+", "-"):
            operator = self.expect(self.current.kind).value
            node = BinOp(node, operator, self.multiplicative(), line=node.line)
        return node

    def multiplicative(self) -> Expr:
        node = self.unary()
        while self.current.kind in ("*", "/"):
            operator = self.expect(self.current.kind).value
            node = BinOp(node, operator, self.unary(), line=node.line)
        return node

    def unary(self) -> Expr:
        if self.current.kind == "-":
            token = self.expect("-")
            return UnaryOp("-", self.unary(), line=token.line)
        return self.power()

    def power(self) -> Expr:
        node = self.primary()
        if self.current.kind == "^":
            self.expect("^")
            # Recursion through unary permits 2^-3 and groups 2^3^4 as 2^(3^4).
            node = BinOp(node, "^", self.unary(), line=node.line)
        return node

    def primary(self) -> Expr:
        if self.current.kind == "NUMBER":
            token = self.expect("NUMBER")
            literal = token.value
            value = float(literal) if any(c in literal for c in ".eE") else int(literal)
            return Num(value, line=token.line)
        if self.current.kind == "IDENT":
            token = self.expect("IDENT")
            name = token.value
            if self.current.kind != "(":
                return Var(name, line=token.line)
            self.expect("(")
            arguments = []
            if self.current.kind != ")":
                arguments.append(self.expression())
                while self.current.kind == ",":
                    self.expect(",")
                    arguments.append(self.expression())
            self.expect(")")
            return Call(name, arguments, line=token.line)
        if self.current.kind == "(":
            self.expect("(")
            node = self.expression()
            self.expect(")")
            return node
        raise self.error("an expression (number, identifier, '-' or '(')")
