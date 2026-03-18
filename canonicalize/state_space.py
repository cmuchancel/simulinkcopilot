"""Linear state-space extraction from first-order systems."""

from __future__ import annotations

import sympy

from canonicalize.linearity_check import analyze_first_order_linearity
from ir.equation_dict import matrix_to_dict
from latex_frontend.symbols import DeterministicCompileError


def build_state_space_system(first_order_system: dict[str, object]) -> dict[str, object]:
    """Construct a linear state-space representation when the first-order system is linear."""
    analysis = analyze_first_order_linearity(first_order_system)
    if not analysis["is_linear"]:
        offending = analysis["offending_entries"][0]
        raise DeterministicCompileError(
            "First-order system is not linear in states and inputs; "
            f"state {offending['state']!r} retains dependence on {offending['depends_on']}."
        )

    states = list(first_order_system["states"])  # type: ignore[index]
    inputs = list(first_order_system["inputs"])  # type: ignore[index]
    A = analysis["A"]
    B = analysis["B"]
    offset = analysis["offset"]
    C = sympy.eye(len(states))
    D = sympy.Matrix.zeros(len(states), len(inputs))
    return {
        "states": states,
        "inputs": inputs,
        "parameters": list(first_order_system["parameters"]),  # type: ignore[index]
        "A": matrix_to_dict(A),
        "B": matrix_to_dict(B),
        "C": matrix_to_dict(C),
        "D": matrix_to_dict(D),
        "offset": matrix_to_dict(offset),
    }
