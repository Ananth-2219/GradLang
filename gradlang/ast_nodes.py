"""Plain data classes describing syntax, without evaluation or type checking."""

from dataclasses import dataclass, field
from typing import List, Union


@dataclass
class Num:
    value: Union[int, float]
    line: int = field(default=0, compare=False)


@dataclass
class Var:
    name: str
    line: int = field(default=0, compare=False)


@dataclass
class UnaryOp:
    operator: str
    operand: "Expr"
    line: int = field(default=0, compare=False)


@dataclass
class BinOp:
    left: "Expr"
    operator: str
    right: "Expr"
    line: int = field(default=0, compare=False)


@dataclass
class Call:
    name: str
    arguments: List["Expr"]
    line: int = field(default=0, compare=False)


Expr = Union[Num, Var, UnaryOp, BinOp, Call]


@dataclass
class Assign:
    name: str
    value: Expr
    line: int = field(default=0, compare=False)


@dataclass
class Return:
    value: Expr
    line: int = field(default=0, compare=False)


@dataclass
class FunctionDef:
    name: str
    params: List[str]
    body: List[Union[Assign, Return]]
    line: int = field(default=0, compare=False)
