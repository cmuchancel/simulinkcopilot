"""Deterministically isolate highest-order derivatives."""

from __future__ import annotations

from dataclasses import dataclass

import sympy

from ir_v2.equation_dict import equation_to_residual, sympy_to_expression
from ir_v2.expression_nodes import EquationNode
from latex_frontend_v2.symbols import DeterministicCompileError, derivative_symbol_name
from states_v2.rules import collect_derivative_orders


@dataclass(frozen=True)
class SolvedDerivative:
    """A solved highest-order derivative equation."""

    base: str
    order: int
    equation: EquationNode

    def to_dict(self) -> dict[str, object]:
        from ir_v2.equation_dict import equation_to_dict

        return {
            "base": self.base,
            "order": self.order,
            "equation": equation_to_dict(self.equation),
        }


def solve_for_highest_derivatives(equations: list[EquationNode]) -> list[SolvedDerivative]:
    """Solve the system for the highest-order derivative of each base state."""
    derivative_orders = collect_derivative_orders(equations)
    targets = [
        (base, order, sympy.Symbol(derivative_symbol_name(base, order)))
        for base, order in sorted(derivative_orders.items())
        if order > 0
    ]
    if not targets:
        raise DeterministicCompileError("No derivatives found to solve for.")

    residuals = [equation_to_residual(equation) for equation in equations]
    target_symbols = [target_symbol for _, _, target_symbol in targets]

    if len(residuals) < len(target_symbols):
        raise DeterministicCompileError(
            "Underdetermined system: fewer equations than highest-order derivative targets."
        )

    residual_target_sets = [set(residual.free_symbols) & set(target_symbols) for residual in residuals]
    for index, symbols in enumerate(residual_target_sets):
        if not symbols:
            raise DeterministicCompileError(
                f"Equation {index} does not contain a highest-order derivative target; "
                "algebraic/DAE-like constraints are unsupported."
            )

    try:
        solutions = sympy.solve(
            residuals,
            target_symbols,
            dict=True,
            simplify=True,
        )
    except NotImplementedError as exc:
        raise DeterministicCompileError(
            "Failed to isolate highest-order derivatives; implicit nonlinear derivative coupling is unsupported."
        ) from exc

    if not solutions:
        if len(residuals) > len(target_symbols):
            raise DeterministicCompileError(
                "Overdetermined or inconsistent system: no deterministic solution for highest-order derivatives."
            )
        raise DeterministicCompileError(
            "Failed to isolate highest-order derivatives; implicit nonlinear derivative coupling is unsupported."
        )

    if len(solutions) != 1:
        raise DeterministicCompileError(
            f"Expected exactly one deterministic solution for highest derivatives, found {len(solutions)}."
        )

    solution = solutions[0]
    solved: list[SolvedDerivative] = []
    for base, order, target_symbol in targets:
        if target_symbol not in solution:
            raise DeterministicCompileError(
                f"Failed to isolate highest derivative {target_symbol.name}."
            )
        rhs_expr = sympy.simplify(solution[target_symbol])
        if set(rhs_expr.free_symbols) & set(target_symbols):
            raise DeterministicCompileError(
                f"Highest derivative {target_symbol.name} remains implicitly coupled to other targets."
            )
        solved.append(
            SolvedDerivative(
                base=base,
                order=order,
                equation=EquationNode(
                    lhs=sympy_to_expression(target_symbol),
                    rhs=sympy_to_expression(rhs_expr),
                ),
            )
        )

    residual_check = [sympy.simplify(residual.subs(solution)) for residual in residuals]
    unresolved: list[str] = []
    for expr in residual_check:
        if expr == 0:
            continue
        try:
            normalized = sympy.simplify(sympy.nsimplify(expr))
        except ValueError:
            normalized = expr
        if normalized != 0:
            unresolved.append(sympy.sstr(normalized))
    if unresolved:
        raise DeterministicCompileError(
            "System retains unresolved algebraic constraints after solving derivatives: "
            + "; ".join(unresolved)
        )

    return solved
