"""Expression node definitions for deterministic equation IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class NumberNode:
    value: int | float


@dataclass(frozen=True)
class SymbolNode:
    name: str


@dataclass(frozen=True)
class DerivativeNode:
    base: str
    order: int


@dataclass(frozen=True)
class AddNode:
    args: tuple["ExpressionNode", ...]


@dataclass(frozen=True)
class MulNode:
    args: tuple["ExpressionNode", ...]


@dataclass(frozen=True)
class DivNode:
    numerator: "ExpressionNode"
    denominator: "ExpressionNode"


@dataclass(frozen=True)
class PowNode:
    base: "ExpressionNode"
    exponent: "ExpressionNode"


@dataclass(frozen=True)
class NegNode:
    operand: "ExpressionNode"


@dataclass(frozen=True)
class FunctionNode:
    function: str
    operand: "ExpressionNode"


@dataclass(frozen=True)
class EquationNode:
    lhs: "ExpressionNode"
    rhs: "ExpressionNode"


ExpressionNode = NumberNode | SymbolNode | DerivativeNode | AddNode | MulNode | DivNode | PowNode | NegNode | FunctionNode


def flatten_add(args: Iterable[ExpressionNode]) -> tuple[ExpressionNode, ...]:
    """Flatten nested additions while preserving operand order."""
    flat: list[ExpressionNode] = []
    for arg in args:
        if isinstance(arg, AddNode):
            flat.extend(arg.args)
        else:
            flat.append(arg)
    return tuple(flat)


def flatten_mul(args: Iterable[ExpressionNode]) -> tuple[ExpressionNode, ...]:
    """Flatten nested multiplications while preserving operand order."""
    flat: list[ExpressionNode] = []
    for arg in args:
        if isinstance(arg, MulNode):
            flat.extend(arg.args)
        else:
            flat.append(arg)
    return tuple(flat)


def walk_expression(node: ExpressionNode) -> list[ExpressionNode]:
    """Return a preorder traversal of an expression tree."""
    nodes = [node]
    if isinstance(node, (NumberNode, SymbolNode, DerivativeNode)):
        return nodes
    if isinstance(node, AddNode):
        for child in node.args:
            nodes.extend(walk_expression(child))
    elif isinstance(node, MulNode):
        for child in node.args:
            nodes.extend(walk_expression(child))
    elif isinstance(node, DivNode):
        nodes.extend(walk_expression(node.numerator))
        nodes.extend(walk_expression(node.denominator))
    elif isinstance(node, PowNode):
        nodes.extend(walk_expression(node.base))
        nodes.extend(walk_expression(node.exponent))
    elif isinstance(node, NegNode):
        nodes.extend(walk_expression(node.operand))
    elif isinstance(node, FunctionNode):
        nodes.extend(walk_expression(node.operand))
    return nodes
