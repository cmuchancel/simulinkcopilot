"""Deterministically isolate highest-order derivatives."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Collection

import sympy

from canonicalize.dae_reduction import reduce_semi_explicit_dae
from ir.equation_dict import equation_to_residual, equation_to_string, sympy_to_expression
from ir.expression_nodes import EquationNode
from latex_frontend.symbols import DeterministicCompileError, derivative_symbol_name
from states.rules import collect_derivative_orders


@dataclass(frozen=True)
class SolvedDerivative:
    """A solved highest-order derivative equation."""

    base: str
    order: int
    equation: EquationNode

    def to_dict(self) -> dict[str, object]:
        from ir.equation_dict import equation_to_dict

        return {
            "base": self.base,
            "order": self.order,
            "equation": equation_to_dict(self.equation),
        }


def solve_for_highest_derivatives(
    equations: list[EquationNode],
    *,
    protected_symbols: Collection[str] = (),
) -> list[SolvedDerivative]:
    """Solve the system for the highest-order derivative of each base state."""
    reduction = reduce_semi_explicit_dae(equations, protected_symbols=protected_symbols)
    resolved_equations = reduction.equations
    derivative_orders = collect_derivative_orders(resolved_equations)
    if not derivative_orders:
        raise DeterministicCompileError("No derivatives found to solve for.")
    if reduction.residual_constraints:
        constraint_summary = "; ".join(
            equation_to_string(equation)
            for equation in reduction.residual_constraints
        )
        raise DeterministicCompileError(
            "Algebraic/DAE-like constraints are unsupported in the explicit ODE pipeline: "
            + constraint_summary
        )
    targets = [
        (base, order, sympy.Symbol(derivative_symbol_name(base, order)))
        for base, order in sorted(derivative_orders.items())
        if order > 0
    ]
    if not targets:
        raise DeterministicCompileError("No derivatives found to solve for.")

    residuals = [equation_to_residual(equation) for equation in resolved_equations]
    target_symbols = [target_symbol for _, _, target_symbol in targets]

    if len(residuals) < len(target_symbols):
        raise DeterministicCompileError(
            "Underdetermined system: fewer equations than highest-order derivative targets."
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
