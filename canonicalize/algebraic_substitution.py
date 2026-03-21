"""Deterministically inline algebraic helper definitions into dynamic equations."""

from __future__ import annotations

from dataclasses import dataclass

import sympy

from ir.equation_dict import equation_to_sympy, sympy_to_equation, sympy_to_expression
from ir.expression_nodes import EquationNode, SymbolNode
from latex_frontend.symbols import DeterministicCompileError
from states.rules import collect_derivative_orders


@dataclass(frozen=True)
class AlgebraicSubstitutionResult:
    """Expanded equation set plus the resolved helper definitions that were inlined."""

    equations: list[EquationNode]
    resolved_definitions: dict[str, EquationNode]


def inline_algebraic_definitions(equations: list[EquationNode]) -> AlgebraicSubstitutionResult:
    """Inline plain-symbol algebraic definitions into the remaining equations."""
    derivative_orders = collect_derivative_orders(equations)
    definitions: dict[str, sympy.Expr] = {}
    passthrough: list[EquationNode] = []

    for equation in equations:
        if _is_algebraic_definition(equation, derivative_orders):
            assert isinstance(equation.lhs, SymbolNode)  # narrowed by _is_algebraic_definition
            symbol_name = equation.lhs.name
            if symbol_name in definitions:
                raise DeterministicCompileError(
                    f"Symbol {symbol_name!r} is defined algebraically more than once."
                )
            definitions[symbol_name] = sympy.simplify(equation_to_sympy(equation).rhs)
            continue
        passthrough.append(equation)

    if not definitions:
        return AlgebraicSubstitutionResult(
            equations=list(equations),
            resolved_definitions={},
        )

    resolved_exprs: dict[str, sympy.Expr] = {}
    visiting: list[str] = []

    def resolve(symbol_name: str) -> sympy.Expr:
        if symbol_name in resolved_exprs:
            return resolved_exprs[symbol_name]
        if symbol_name in visiting:
            cycle = " -> ".join([*visiting, symbol_name])
            raise DeterministicCompileError(
                f"Cyclic algebraic helper definitions are unsupported: {cycle}."
            )

        visiting.append(symbol_name)
        try:
            resolved = definitions[symbol_name]
            for dependency in sorted(
                helper_name
                for helper_name in {symbol.name for symbol in resolved.free_symbols}
                if helper_name in definitions
            ):
                resolved = sympy.simplify(
                    resolved.subs(
                        sympy.Symbol(dependency),
                        resolve(dependency),
                        simultaneous=True,
                    )
                )
            if sympy.Symbol(symbol_name) in resolved.free_symbols:
                raise DeterministicCompileError(
                    f"Algebraic helper definition for {symbol_name!r} references itself after substitution."
                )
            resolved_exprs[symbol_name] = sympy.simplify(resolved)
            return resolved_exprs[symbol_name]
        finally:
            visiting.pop()

    for symbol_name in definitions:
        resolve(symbol_name)

    substitution_map = {
        sympy.Symbol(symbol_name): resolved_expr
        for symbol_name, resolved_expr in resolved_exprs.items()
    }
    expanded_equations = [
        sympy_to_equation(
            lhs=sympy.simplify(_substitute(expression=equation_to_sympy(equation).lhs, substitutions=substitution_map)),
            rhs=sympy.simplify(_substitute(expression=equation_to_sympy(equation).rhs, substitutions=substitution_map)),
        )
        for equation in passthrough
    ]
    resolved_definitions = {
        symbol_name: EquationNode(
            lhs=SymbolNode(symbol_name),
            rhs=sympy_to_expression(resolved_expr),
        )
        for symbol_name, resolved_expr in resolved_exprs.items()
    }
    return AlgebraicSubstitutionResult(
        equations=expanded_equations,
        resolved_definitions=resolved_definitions,
    )


def _is_algebraic_definition(equation: EquationNode, derivative_orders: dict[str, int]) -> bool:
    if not isinstance(equation.lhs, SymbolNode):
        return False
    if equation.lhs.name == "t":
        return False
    return derivative_orders.get(equation.lhs.name, 0) == 0


def _substitute(*, expression: sympy.Expr, substitutions: dict[sympy.Symbol, sympy.Expr]) -> sympy.Expr:
    if not substitutions:
        return expression
    return expression.subs(substitutions, simultaneous=True)
