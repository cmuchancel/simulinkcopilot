"""Conversion from solved higher-order systems to first-order state equations."""

from __future__ import annotations

import sympy

from canonicalize.solve_for_derivatives import SolvedDerivative, solve_for_highest_derivatives
from ir.equation_dict import expression_from_dict, expression_to_dict, expression_to_sympy, sympy_to_expression
from ir.expression_nodes import EquationNode, SymbolNode
from latex_frontend.symbols import derivative_symbol_name, state_name
from states.extract_states import analyze_state_extraction, extract_states
from states.rules import ExtractionResult


def build_first_order_system(
    equations: list[EquationNode],
    extraction: ExtractionResult | None = None,
    solved_derivatives: list[SolvedDerivative] | None = None,
) -> dict[str, object]:
    """Build a canonical first-order state-equation system."""
    if extraction is None and solved_derivatives is None:
        analysis = analyze_state_extraction(equations)
        extraction = analysis.extraction
        solved_derivatives = analysis.solved_derivatives

    extraction = extraction or extract_states(equations)
    solved_derivatives = solved_derivatives or solve_for_highest_derivatives(equations)

    solved_map = {
        (item.base, item.order): expression_to_sympy(item.equation.rhs)
        for item in solved_derivatives
    }

    substitution_map: dict[sympy.Symbol, sympy.Symbol] = {}
    for base, max_order in extraction.derivative_orders.items():
        substitution_map[sympy.Symbol(base)] = sympy.Symbol(state_name(base, 0))
        for order in range(1, max_order):
            substitution_map[sympy.Symbol(derivative_symbol_name(base, order))] = sympy.Symbol(state_name(base, order))

    state_equations: list[dict[str, object]] = []
    for base, max_order in sorted(extraction.derivative_orders.items()):
        if max_order == 1:
            rhs_expr = sympy.simplify(solved_map[(base, 1)].xreplace(substitution_map))
            state_equations.append(
                {
                    "state": state_name(base, 0),
                    "rhs": expression_to_dict(sympy_to_expression(rhs_expr)),
                }
            )
            continue

        for order in range(max_order - 1):
            state_equations.append(
                {
                    "state": state_name(base, order),
                    "rhs": expression_to_dict(SymbolNode(state_name(base, order + 1))),
                }
            )

        final_rhs = sympy.simplify(solved_map[(base, max_order)].xreplace(substitution_map))
        state_equations.append(
            {
                "state": state_name(base, max_order - 1),
                "rhs": expression_to_dict(sympy_to_expression(final_rhs)),
            }
        )

    return {
        "states": list(extraction.states),
        "inputs": list(extraction.inputs),
        "parameters": list(extraction.parameters),
        "independent_variable": extraction.independent_variable,
        "state_equations": state_equations,
    }


def first_order_rhs_sympy(system: dict[str, object]) -> list[sympy.Expr]:
    """Return the state-equation RHS expressions as SymPy expressions."""
    return [
        expression_to_sympy(expression_from_dict(entry["rhs"]))  # type: ignore[arg-type]
        for entry in system["state_equations"]  # type: ignore[index]
    ]
