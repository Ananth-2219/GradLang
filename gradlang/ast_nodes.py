"""Plain data classes describing syntax, without evaluation or type checking."""

from dataclasses import dataclass
from typing import List, Union


@dataclass
class Num:
    value: Union[int, float]


@dataclass
class Var:
    name: str


@dataclass
class UnaryOp:
    operator: str
    operand: "Expr"


@dataclass
class BinOp:
    left: "Expr"
    operator: str
    right: "Expr"


@dataclass
class Call:
    name: str
    arguments: List["Expr"]


Expr = Union[Num, Var, UnaryOp, BinOp, Call]


@dataclass
class Assign:
    name: str
    value: Expr


@dataclass
class Return:
    value: Expr


@dataclass
class FunctionDef:
    name: str
    params: List[str]
    body: List[Union[Assign, Return]]
