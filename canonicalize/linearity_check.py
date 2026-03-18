"""Linearity analysis for first-order deterministic systems."""

from __future__ import annotations

import sympy

from canonicalize.first_order import first_order_rhs_sympy


def analyze_first_order_linearity(first_order_system: dict[str, object]) -> dict[str, object]:
    """Return linearity metadata for a first-order system."""
    states = [sympy.Symbol(name) for name in first_order_system["states"]]  # type: ignore[index]
    inputs = [sympy.Symbol(name) for name in first_order_system["inputs"]]  # type: ignore[index]
    rhs_matrix = sympy.Matrix(first_order_rhs_sympy(first_order_system))
    state_vector = sympy.Matrix(states)
    input_vector = sympy.Matrix(inputs) if inputs else sympy.Matrix.zeros(0, 0)

    A = rhs_matrix.jacobian(states)
    B = rhs_matrix.jacobian(inputs) if inputs else sympy.Matrix.zeros(len(states), 0)
    offset = sympy.simplify(
        rhs_matrix - A * state_vector - (B * input_vector if inputs else sympy.Matrix.zeros(len(states), 1))
    )

    offending_entries: list[dict[str, object]] = []
    state_and_input_symbols = set(states) | set(inputs)
    for index, entry in enumerate(offset):
        offending = sorted(symbol.name for symbol in entry.free_symbols & state_and_input_symbols)
        if offending:
            offending_entries.append(
                {
                    "state": first_order_system["states"][index],  # type: ignore[index]
                    "expr": sympy.sstr(entry),
                    "depends_on": offending,
                }
            )

    return {
        "is_linear": not offending_entries,
        "A": A,
        "B": B,
        "offset": offset,
        "offending_entries": offending_entries,
    }
