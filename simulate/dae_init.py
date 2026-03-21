"""Consistent initialization helpers for reducible semi-explicit DAE systems."""

from __future__ import annotations

from dataclasses import dataclass

import sympy

from canonicalize.dae_system import SemiExplicitDaeSystem
from ir.equation_dict import expression_to_sympy
from latex_frontend.symbols import DeterministicCompileError
from simulate.ode_sim import InputFunction


@dataclass(frozen=True)
class ConsistentInitializationResult:
    """Resolved initial conditions for differential and algebraic variables."""

    differential_initial_conditions: dict[str, float]
    algebraic_initial_conditions: dict[str, float]
    reduced_to_explicit: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "differential_initial_conditions": dict(self.differential_initial_conditions),
            "algebraic_initial_conditions": dict(self.algebraic_initial_conditions),
            "reduced_to_explicit": self.reduced_to_explicit,
        }


def consistent_initialize_dae(
    dae_system: SemiExplicitDaeSystem,
    *,
    parameter_values: dict[str, float],
    differential_initial_conditions: dict[str, float],
    input_function: InputFunction | None = None,
    independent_variable: str | None = None,
    t0: float = 0.0,
) -> ConsistentInitializationResult:
    """Compute algebraic initial conditions for reducible semi-explicit DAE systems."""
    normalized_differential = {
        state: float(differential_initial_conditions.get(state, 0.0))
        for state in dae_system.differential_states
    }
    if not dae_system.algebraic_variables:
        return ConsistentInitializationResult(
            differential_initial_conditions=normalized_differential,
            algebraic_initial_conditions={},
            reduced_to_explicit=True,
        )
    if not dae_system.reduced_to_explicit:
        raise DeterministicCompileError(
            "Consistent initialization currently requires a reducible semi-explicit DAE system."
        )

    input_function = input_function or (lambda _time: {})
    substitution_values: dict[sympy.Symbol, float] = {
        sympy.Symbol(name): float(value)
        for name, value in parameter_values.items()
    }
    substitution_values.update(
        {
            sympy.Symbol(name): value
            for name, value in normalized_differential.items()
        }
    )
    substitution_values.update(
        {
            sympy.Symbol(name): float(value)
            for name, value in input_function(t0).items()
        }
    )
    if independent_variable is not None:
        substitution_values[sympy.Symbol(independent_variable)] = float(t0)

    algebraic_initials: dict[str, float] = {}
    for name, equation in dae_system.solved_algebraic_variables.items():
        rhs_expr = expression_to_sympy(equation.rhs)
        unresolved = {
            symbol.name
            for symbol in rhs_expr.free_symbols
            if symbol not in substitution_values
        }
        if unresolved:
            raise DeterministicCompileError(
                f"Cannot consistently initialize algebraic variable {name!r}; missing values for {sorted(unresolved)}."
            )
        algebraic_initials[name] = float(sympy.N(rhs_expr.subs(substitution_values)))
        substitution_values[sympy.Symbol(name)] = algebraic_initials[name]

    return ConsistentInitializationResult(
        differential_initial_conditions=normalized_differential,
        algebraic_initial_conditions=algebraic_initials,
        reduced_to_explicit=True,
    )
