"""Deterministic reduction of reducible semi-explicit DAEs into explicit ODE systems."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

import sympy

from canonicalize.algebraic_substitution import classify_algebraic_equations, inline_algebraic_definitions
from ir.equation_dict import equation_to_residual, equation_to_sympy, sympy_to_equation, sympy_to_expression
from ir.expression_nodes import EquationNode, SymbolNode
from latex_frontend.symbols import derivative_symbol_name
from states.rules import collect_derivative_orders


@dataclass(frozen=True)
class DaeReductionResult:
    """Reduced equation set plus any helper/algebraic substitutions applied."""

    equations: list[EquationNode]
    dynamic_equations: list[EquationNode]
    reduced_dynamic_equations: list[EquationNode]
    algebraic_constraints: list[EquationNode]
    resolved_helper_definitions: dict[str, EquationNode]
    solved_algebraic_variables: dict[str, EquationNode]
    residual_constraints: list[EquationNode]
    algebraic_variables: tuple[str, ...]


def reduce_semi_explicit_dae(
    equations: list[EquationNode],
    *,
    protected_symbols: Collection[str] = (),
) -> DaeReductionResult:
    """Reduce a semi-explicit DAE to an explicit ODE when algebraic variables are solvable."""
    substitution = inline_algebraic_definitions(equations)
    classification = classify_algebraic_equations(substitution.equations)
    if not classification.algebraic_constraints:
        return DaeReductionResult(
            equations=substitution.equations,
            dynamic_equations=list(classification.dynamic_equations),
            reduced_dynamic_equations=list(classification.dynamic_equations),
            algebraic_constraints=[],
            resolved_helper_definitions=substitution.resolved_definitions,
            solved_algebraic_variables={},
            residual_constraints=[],
            algebraic_variables=(),
        )

    candidate_names = _candidate_algebraic_variables(
        dynamic_equations=classification.dynamic_equations,
        algebraic_constraints=classification.algebraic_constraints,
        protected_symbols=set(protected_symbols),
    )
    if not candidate_names:
        return DaeReductionResult(
            equations=substitution.equations,
            dynamic_equations=list(classification.dynamic_equations),
            reduced_dynamic_equations=list(classification.dynamic_equations),
            algebraic_constraints=list(classification.algebraic_constraints),
            resolved_helper_definitions=substitution.resolved_definitions,
            solved_algebraic_variables={},
            residual_constraints=list(classification.algebraic_constraints),
            algebraic_variables=(),
        )

    solved_algebraic_variables = _solve_algebraic_variables(
        algebraic_constraints=classification.algebraic_constraints,
        candidate_names=candidate_names,
    )
    if not solved_algebraic_variables:
        return DaeReductionResult(
            equations=substitution.equations,
            dynamic_equations=list(classification.dynamic_equations),
            reduced_dynamic_equations=list(classification.dynamic_equations),
            algebraic_constraints=list(classification.algebraic_constraints),
            resolved_helper_definitions=substitution.resolved_definitions,
            solved_algebraic_variables={},
            residual_constraints=list(classification.algebraic_constraints),
            algebraic_variables=tuple(candidate_names),
        )

    substitution_map = {
        sympy.Symbol(symbol_name): equation_to_sympy(equation).rhs
        for symbol_name, equation in solved_algebraic_variables.items()
    }
    reduced_dynamic = [
        _substitute_equation(equation, substitution_map)
        for equation in classification.dynamic_equations
    ]
    reduced_constraints = [
        reduced_equation
        for reduced_equation in (
            _substitute_equation(equation, substitution_map)
            for equation in classification.algebraic_constraints
        )
        if sympy.simplify(equation_to_residual(reduced_equation)) != 0
    ]

    return DaeReductionResult(
        equations=[*reduced_dynamic, *reduced_constraints],
        dynamic_equations=list(classification.dynamic_equations),
        reduced_dynamic_equations=reduced_dynamic,
        algebraic_constraints=list(classification.algebraic_constraints),
        resolved_helper_definitions=substitution.resolved_definitions,
        solved_algebraic_variables=solved_algebraic_variables,
        residual_constraints=reduced_constraints,
        algebraic_variables=tuple(candidate_names),
    )


def _candidate_algebraic_variables(
    *,
    dynamic_equations: list[EquationNode],
    algebraic_constraints: list[EquationNode],
    protected_symbols: set[str],
) -> list[str]:
    derivative_orders = collect_derivative_orders([*dynamic_equations, *algebraic_constraints])
    state_bases = set(derivative_orders)
    derivative_symbol_names = {
        derivative_symbol_name(base, order)
        for base, max_order in derivative_orders.items()
        for order in range(1, max_order + 1)
    }
    protected = set(protected_symbols) | state_bases | derivative_symbol_names

    dynamic_symbols = set().union(
        *(equation_to_sympy(equation).free_symbols for equation in dynamic_equations),
    ) if dynamic_equations else set()
    constraint_symbols = set().union(
        *(equation_to_residual(equation).free_symbols for equation in algebraic_constraints),
    ) if algebraic_constraints else set()

    return sorted(
        symbol.name
        for symbol in dynamic_symbols & constraint_symbols
        if symbol.name not in protected
    )


def _solve_algebraic_variables(
    *,
    algebraic_constraints: list[EquationNode],
    candidate_names: list[str],
) -> dict[str, EquationNode]:
    if not candidate_names:
        return {}

    candidate_symbols = [sympy.Symbol(name) for name in candidate_names]
    residuals = [equation_to_residual(equation) for equation in algebraic_constraints]
    try:
        solutions = sympy.solve(
            residuals,
            candidate_symbols,
            dict=True,
            simplify=True,
        )
    except NotImplementedError:
        return {}

    if len(solutions) != 1:
        return {}

    raw_solution = {
        symbol.name: sympy.simplify(expr)
        for symbol, expr in solutions[0].items()
        if symbol.name in candidate_names
    }
    if not raw_solution:
        return {}

    resolved_exprs = _resolve_solution_map(raw_solution, candidate_names)
    return {
        symbol_name: EquationNode(
            lhs=SymbolNode(symbol_name),
            rhs=sympy_to_expression(resolved_expr),
        )
        for symbol_name, resolved_expr in resolved_exprs.items()
    }


def _resolve_solution_map(
    raw_solution: dict[str, sympy.Expr],
    candidate_names: list[str],
) -> dict[str, sympy.Expr]:
    resolved_exprs: dict[str, sympy.Expr] = {}
    visiting: list[str] = []
    candidate_name_set = set(candidate_names)

    def resolve(symbol_name: str) -> sympy.Expr:
        if symbol_name in resolved_exprs:
            return resolved_exprs[symbol_name]
        if symbol_name in visiting:
            raise ValueError("Cyclic algebraic solution dependencies are unsupported.")

        visiting.append(symbol_name)
        try:
            resolved = raw_solution[symbol_name]
            for dependency in sorted(
                dep_name
                for dep_name in {symbol.name for symbol in resolved.free_symbols}
                if dep_name in raw_solution
            ):
                resolved = sympy.simplify(
                    resolved.subs(
                        sympy.Symbol(dependency),
                        resolve(dependency),
                        simultaneous=True,
                    )
                )
            if sympy.Symbol(symbol_name) in resolved.free_symbols:
                raise ValueError("Self-referential algebraic solutions are unsupported.")
            unresolved_candidates = {
                symbol.name
                for symbol in resolved.free_symbols
                if symbol.name in candidate_name_set and symbol.name not in raw_solution
            }
            if unresolved_candidates:
                raise ValueError("Solution retains unresolved algebraic variables.")
            resolved_exprs[symbol_name] = sympy.simplify(resolved)
            return resolved_exprs[symbol_name]
        finally:
            visiting.pop()

    try:
        for symbol_name in raw_solution:
            resolve(symbol_name)
    except ValueError:
        return {}
    return resolved_exprs


def _substitute_equation(
    equation: EquationNode,
    substitutions: dict[sympy.Symbol, sympy.Expr],
) -> EquationNode:
    lhs = sympy.simplify(equation_to_sympy(equation).lhs.subs(substitutions, simultaneous=True))
    rhs = sympy.simplify(equation_to_sympy(equation).rhs.subs(substitutions, simultaneous=True))
    return sympy_to_equation(lhs=lhs, rhs=rhs)
