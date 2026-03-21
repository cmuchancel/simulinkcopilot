"""Helpers for explicit nonlinear first-order system metadata."""

from __future__ import annotations

from ir.equation_dict import expression_from_dict, expression_to_sympy


def build_explicit_system_form(first_order_system: dict[str, object]) -> dict[str, object]:
    """Return an explicit deterministic description of the first-order RHS."""
    rhs = {
        entry["state"]: expression_to_sympy(expression_from_dict(entry["rhs"]))  # type: ignore[arg-type]
        for entry in first_order_system["state_equations"]  # type: ignore[index]
    }
    return {
        "form": "explicit_first_order",
        "states": list(first_order_system["states"]),  # type: ignore[index]
        "inputs": list(first_order_system["inputs"]),  # type: ignore[index]
        "parameters": list(first_order_system["parameters"]),  # type: ignore[index]
        "independent_variable": first_order_system.get("independent_variable"),
        "rhs": rhs,
    }
