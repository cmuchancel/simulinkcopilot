"""Deterministically inline algebraic helper definitions into dynamic equations."""

from __future__ import annotations

from dataclasses import dataclass

import sympy

from ir.equation_dict import equation_to_sympy, sympy_to_equation, sympy_to_expression
from ir.expression_nodes import EquationNode, SymbolNode
from latex_frontend.symbols import DeterministicCompileError
from states.rules import collect_derivative_orders


@dataclass(frozen=True)
class AlgebraicEquationClassification:
    """Partition equations into helper definitions, algebraic constraints, and dynamic equations."""

    helper_definitions: dict[str, EquationNode]
    algebraic_constraints: list[EquationNode]
    dynamic_equations: list[EquationNode]


@dataclass(frozen=True)
class AlgebraicSubstitutionResult:
    """Expanded equation set plus the resolved helper definitions that were inlined."""

    equations: list[EquationNode]
    resolved_definitions: dict[str, EquationNode]
    algebraic_constraints: list[EquationNode]


def classify_algebraic_equations(equations: list[EquationNode]) -> AlgebraicEquationClassification:
    """Identify explicit helper definitions separately from genuine algebraic constraints."""
    helper_definitions: dict[str, EquationNode] = {}
    algebraic_constraints: list[EquationNode] = []
    dynamic_equations: list[EquationNode] = []

    for equation in equations:
        if _is_algebraic_definition(equation):
            assert isinstance(equation.lhs, SymbolNode)  # narrowed by _is_algebraic_definition
            symbol_name = equation.lhs.name
            if symbol_name in helper_definitions:
                raise DeterministicCompileError(
                    f"Symbol {symbol_name!r} is defined algebraically more than once."
                )
            helper_definitions[symbol_name] = equation
            continue
        if _is_algebraic_constraint(equation):
            algebraic_constraints.append(equation)
            continue
        dynamic_equations.append(equation)

    return AlgebraicEquationClassification(
        helper_definitions=helper_definitions,
        algebraic_constraints=algebraic_constraints,
        dynamic_equations=dynamic_equations,
    )


def inline_algebraic_definitions(equations: list[EquationNode]) -> AlgebraicSubstitutionResult:
    """Inline plain-symbol algebraic definitions into the remaining equations."""
    classification = classify_algebraic_equations(equations)
    definitions: dict[str, sympy.Expr] = {}
    passthrough = [*classification.dynamic_equations, *classification.algebraic_constraints]

    for symbol_name, equation in classification.helper_definitions.items():
        definitions[symbol_name] = sympy.simplify(equation_to_sympy(equation).rhs)

    if not definitions:
        return AlgebraicSubstitutionResult(
            equations=list(equations),
            resolved_definitions={},
            algebraic_constraints=list(classification.algebraic_constraints),
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
    expanded_constraints = [
        equation
        for equation in expanded_equations
        if _is_algebraic_constraint(equation)
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
        algebraic_constraints=expanded_constraints,
    )


def _equation_has_derivatives(equation: EquationNode) -> bool:
    return bool(collect_derivative_orders([equation]))


def _is_algebraic_definition(equation: EquationNode) -> bool:
    if not isinstance(equation.lhs, SymbolNode):
        return False
    if equation.lhs.name == "t":
        return False
    return not _equation_has_derivatives(equation)


def _is_algebraic_constraint(equation: EquationNode) -> bool:
    return not _equation_has_derivatives(equation) and not _is_algebraic_definition(equation)


def _substitute(*, expression: sympy.Expr, substitutions: dict[sympy.Symbol, sympy.Expr]) -> sympy.Expr:
    if not substitutions:
        return expression
    return expression.subs(substitutions, simultaneous=True)
