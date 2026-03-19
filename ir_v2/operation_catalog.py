"""Operation catalog for all supported deterministic IR node types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ir_v2.expression_nodes import (
    AddNode,
    DerivativeNode,
    DivNode,
    EquationNode,
    ExpressionNode,
    FunctionNode,
    MulNode,
    NegNode,
    NumberNode,
    PowNode,
    SymbolNode,
)
from latex_frontend_v2.symbols import DeterministicCompileError, SUPPORTED_FUNCTION_NAMES


@dataclass(frozen=True)
class OperationSpec:
    """Metadata for a supported operation."""

    name: str
    arity: str
    block_shell: dict[str, str]


OPERATION_CATALOG: dict[str, OperationSpec] = {
    "const": OperationSpec("const", "literal", {"family": "literal", "shape": "scalar"}),
    "symbol": OperationSpec("symbol", "literal", {"family": "symbol", "shape": "scalar"}),
    "derivative": OperationSpec("derivative", "unary-metadata", {"family": "derivative", "shape": "scalar"}),
    "add": OperationSpec("add", "variadic", {"family": "arithmetic", "block": "sum"}),
    "mul": OperationSpec("mul", "variadic", {"family": "arithmetic", "block": "product"}),
    "div": OperationSpec("div", "binary", {"family": "arithmetic", "block": "quotient"}),
    "pow": OperationSpec("pow", "binary", {"family": "arithmetic", "block": "power"}),
    "neg": OperationSpec("neg", "unary", {"family": "arithmetic", "block": "negate"}),
    "equation": OperationSpec("equation", "binary", {"family": "relation", "block": "equation"}),
}
OPERATION_CATALOG.update(
    {
        name: OperationSpec(name, "unary", {"family": "transcendental", "block": name})
        for name in sorted(SUPPORTED_FUNCTION_NAMES)
    }
)


def node_operation_name(node: ExpressionNode | EquationNode) -> str:
    """Return the canonical operation name for a node instance."""
    if isinstance(node, NumberNode):
        return "const"
    if isinstance(node, SymbolNode):
        return "symbol"
    if isinstance(node, DerivativeNode):
        return "derivative"
    if isinstance(node, AddNode):
        return "add"
    if isinstance(node, MulNode):
        return "mul"
    if isinstance(node, DivNode):
        return "div"
    if isinstance(node, PowNode):
        return "pow"
    if isinstance(node, NegNode):
        return "neg"
    if isinstance(node, FunctionNode):
        return node.function
    if isinstance(node, EquationNode):
        return "equation"
    raise DeterministicCompileError(f"Unsupported IR node type: {type(node).__name__}")


def validate_supported_node(node: ExpressionNode | EquationNode) -> None:
    """Validate that every node in a tree maps to a supported operation."""
    op_name = node_operation_name(node)
    if op_name not in OPERATION_CATALOG:
        raise DeterministicCompileError(f"Unknown operation {op_name!r}.")

    if isinstance(node, EquationNode):
        validate_supported_node(node.lhs)
        validate_supported_node(node.rhs)
        return
    if isinstance(node, AddNode):
        for child in node.args:
            validate_supported_node(child)
        return
    if isinstance(node, MulNode):
        for child in node.args:
            validate_supported_node(child)
        return
    if isinstance(node, DivNode):
        validate_supported_node(node.numerator)
        validate_supported_node(node.denominator)
        return
    if isinstance(node, PowNode):
        validate_supported_node(node.base)
        validate_supported_node(node.exponent)
        return
    if isinstance(node, NegNode):
        validate_supported_node(node.operand)
        return
    if isinstance(node, FunctionNode):
        validate_supported_node(node.operand)


def validate_operation_dict(node_dict: dict[str, Any]) -> None:
    """Validate that a serialized expression dictionary only uses known operations."""
    op_name = node_dict.get("op")
    if op_name not in OPERATION_CATALOG:
        raise DeterministicCompileError(f"Unknown serialized operation {op_name!r}.")

    if op_name in {"const", "symbol", "derivative"}:
        return
    if op_name == "equation":
        validate_operation_dict(node_dict["lhs"])
        validate_operation_dict(node_dict["rhs"])
        return
    for child in node_dict.get("args", []):
        validate_operation_dict(child)
