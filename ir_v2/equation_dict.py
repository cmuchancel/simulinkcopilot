"""Canonical dictionary serialization and SymPy conversion helpers."""

from __future__ import annotations

from typing import Any

import sympy

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
    flatten_add,
    flatten_mul,
)
from ir_v2.operation_catalog import validate_operation_dict, validate_supported_node
from latex_frontend_v2.symbols import (
    derivative_display_name,
    derivative_symbol_name,
    parse_derivative_symbol_name,
    SUPPORTED_FUNCTION_NAMES,
)


_SYMPY_FUNCTIONS: dict[str, object] = {
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "sec": sympy.sec,
    "csc": sympy.csc,
    "cot": sympy.cot,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "sinh": sympy.sinh,
    "cosh": sympy.cosh,
    "tanh": sympy.tanh,
    "sech": sympy.sech,
    "csch": sympy.csch,
    "coth": sympy.coth,
    "asinh": sympy.asinh,
    "acosh": sympy.acosh,
    "atanh": sympy.atanh,
    "exp": sympy.exp,
    "log": sympy.log,
}
_SYMPY_FUNCTIONS_REVERSE = {value: key for key, value in _SYMPY_FUNCTIONS.items()}


def expression_to_dict(node: ExpressionNode) -> dict[str, Any]:
    """Serialize an expression node to the canonical dictionary form."""
    validate_supported_node(node)
    if isinstance(node, NumberNode):
        return {"op": "const", "value": node.value}
    if isinstance(node, SymbolNode):
        return {"op": "symbol", "name": node.name}
    if isinstance(node, DerivativeNode):
        return {"op": "derivative", "base": node.base, "order": node.order}
    if isinstance(node, AddNode):
        return {"op": "add", "args": [expression_to_dict(arg) for arg in node.args]}
    if isinstance(node, MulNode):
        return {"op": "mul", "args": [expression_to_dict(arg) for arg in node.args]}
    if isinstance(node, DivNode):
        return {"op": "div", "args": [expression_to_dict(node.numerator), expression_to_dict(node.denominator)]}
    if isinstance(node, PowNode):
        return {"op": "pow", "args": [expression_to_dict(node.base), expression_to_dict(node.exponent)]}
    if isinstance(node, NegNode):
        return {"op": "neg", "args": [expression_to_dict(node.operand)]}
    if isinstance(node, FunctionNode):
        return {"op": node.function, "args": [expression_to_dict(node.operand)]}
    raise TypeError(f"Unsupported expression node: {type(node).__name__}")


def equation_to_dict(node: EquationNode) -> dict[str, Any]:
    """Serialize an equation node to the canonical dictionary form."""
    validate_supported_node(node)
    return {"op": "equation", "lhs": expression_to_dict(node.lhs), "rhs": expression_to_dict(node.rhs)}


def expression_from_dict(node_dict: dict[str, Any]) -> ExpressionNode:
    """Deserialize a canonical expression dictionary into IR nodes."""
    validate_operation_dict(node_dict)
    op_name = node_dict["op"]
    if op_name == "const":
        return NumberNode(node_dict["value"])
    if op_name == "symbol":
        return SymbolNode(node_dict["name"])
    if op_name == "derivative":
        return DerivativeNode(node_dict["base"], int(node_dict["order"]))
    if op_name == "add":
        return AddNode(flatten_add(expression_from_dict(child) for child in node_dict["args"]))
    if op_name == "mul":
        return MulNode(flatten_mul(expression_from_dict(child) for child in node_dict["args"]))
    if op_name == "div":
        return DivNode(expression_from_dict(node_dict["args"][0]), expression_from_dict(node_dict["args"][1]))
    if op_name == "pow":
        return PowNode(expression_from_dict(node_dict["args"][0]), expression_from_dict(node_dict["args"][1]))
    if op_name == "neg":
        return NegNode(expression_from_dict(node_dict["args"][0]))
    if op_name in SUPPORTED_FUNCTION_NAMES:
        return FunctionNode(op_name, expression_from_dict(node_dict["args"][0]))
    raise TypeError(f"Unsupported serialized expression operation: {op_name}")


def equation_from_dict(node_dict: dict[str, Any]) -> EquationNode:
    """Deserialize a canonical equation dictionary."""
    validate_operation_dict(node_dict)
    if node_dict["op"] != "equation":
        raise TypeError(f"Expected equation dictionary, got {node_dict['op']!r}.")
    return EquationNode(
        lhs=expression_from_dict(node_dict["lhs"]),
        rhs=expression_from_dict(node_dict["rhs"]),
    )


def expression_to_sympy(node: ExpressionNode) -> sympy.Expr:
    """Convert an expression node into a deterministic SymPy expression."""
    if isinstance(node, NumberNode):
        if isinstance(node.value, int):
            return sympy.Integer(node.value)
        return sympy.Float(node.value)
    if isinstance(node, SymbolNode):
        return sympy.Symbol(node.name)
    if isinstance(node, DerivativeNode):
        return sympy.Symbol(derivative_symbol_name(node.base, node.order))
    if isinstance(node, AddNode):
        return sympy.Add(*[expression_to_sympy(arg) for arg in node.args], evaluate=True)
    if isinstance(node, MulNode):
        return sympy.Mul(*[expression_to_sympy(arg) for arg in node.args], evaluate=True)
    if isinstance(node, DivNode):
        return expression_to_sympy(node.numerator) / expression_to_sympy(node.denominator)
    if isinstance(node, PowNode):
        return expression_to_sympy(node.base) ** expression_to_sympy(node.exponent)
    if isinstance(node, NegNode):
        return -expression_to_sympy(node.operand)
    if isinstance(node, FunctionNode):
        return _SYMPY_FUNCTIONS[node.function](expression_to_sympy(node.operand))
    raise TypeError(f"Unsupported expression node: {type(node).__name__}")


def equation_to_sympy(node: EquationNode) -> sympy.Equality:
    """Convert an equation node into a SymPy equality."""
    return sympy.Eq(expression_to_sympy(node.lhs), expression_to_sympy(node.rhs))


def equation_to_residual(node: EquationNode) -> sympy.Expr:
    """Convert an equation into the residual form lhs - rhs."""
    return sympy.simplify(expression_to_sympy(node.lhs) - expression_to_sympy(node.rhs))


def sympy_to_expression(expr: sympy.Expr) -> ExpressionNode:
    """Convert a SymPy expression into deterministic IR nodes."""
    expr = sympy.simplify(expr)

    if expr.is_Number:
        if expr.is_Integer:
            return NumberNode(int(expr))
        return NumberNode(float(expr))

    if expr.is_Symbol:
        derivative_info = parse_derivative_symbol_name(expr.name)
        if derivative_info is not None:
            base, order = derivative_info
            return DerivativeNode(base=base, order=order)
        return SymbolNode(expr.name)

    if expr.is_Add:
        return AddNode(tuple(sympy_to_expression(arg) for arg in expr.as_ordered_terms()))

    numerator, denominator = sympy.fraction(sympy.together(expr))
    if denominator != 1:
        return DivNode(sympy_to_expression(sympy.expand(numerator)), sympy_to_expression(sympy.expand(denominator)))

    if expr.is_Mul:
        args = expr.as_ordered_factors()
        if len(args) == 2 and args[0] == -1:
            return NegNode(sympy_to_expression(args[1]))
        return MulNode(tuple(sympy_to_expression(arg) for arg in args))

    if expr.is_Pow:
        return PowNode(sympy_to_expression(expr.base), sympy_to_expression(expr.exp))

    if expr.func in _SYMPY_FUNCTIONS_REVERSE and len(expr.args) == 1:
        return FunctionNode(_SYMPY_FUNCTIONS_REVERSE[expr.func], sympy_to_expression(expr.args[0]))

    raise TypeError(f"Unsupported SymPy expression for deterministic IR conversion: {expr!r}")


def sympy_to_equation(lhs: sympy.Expr, rhs: sympy.Expr) -> EquationNode:
    """Convert SymPy expressions into an equation node."""
    return EquationNode(lhs=sympy_to_expression(lhs), rhs=sympy_to_expression(rhs))


def matrix_to_dict(matrix: sympy.Matrix) -> list[list[dict[str, Any]]]:
    """Serialize a SymPy matrix of expressions into nested canonical dictionaries."""
    return [[expression_to_dict(sympy_to_expression(matrix[row, col])) for col in range(matrix.cols)] for row in range(matrix.rows)]


def matrix_from_dict(matrix_dict: list[list[dict[str, Any]]]) -> sympy.Matrix:
    """Deserialize a nested canonical matrix representation."""
    return sympy.Matrix(
        [
            [expression_to_sympy(expression_from_dict(entry)) for entry in row]
            for row in matrix_dict
        ]
    )


def expression_to_string(node: ExpressionNode) -> str:
    """Render an expression node using deterministic SymPy printing."""
    return sympy.sstr(expression_to_sympy(node))


def equation_to_string(node: EquationNode) -> str:
    """Render an equation node using deterministic SymPy printing."""
    return f"{expression_to_string(node.lhs)} = {expression_to_string(node.rhs)}"


def derivative_equation_label(base: str, order: int) -> str:
    """Return the standard label for solved derivative outputs."""
    return derivative_display_name(base, order)
