"""Linear descriptor-system extraction for explicit ODEs and first-order semi-explicit DAEs."""

from __future__ import annotations

import sympy

from canonicalize.dae_system import SemiExplicitDaeSystem
from ir.equation_dict import equation_to_residual, matrix_to_dict
from latex_frontend.symbols import DeterministicCompileError, derivative_symbol_name
from states.rules import ExtractionResult


def build_descriptor_system_from_first_order(first_order_system: dict[str, object]) -> dict[str, object]:
    """Construct a linear descriptor system for an explicit first-order ODE."""
    from canonicalize.linearity_check import analyze_first_order_linearity

    analysis = analyze_first_order_linearity(first_order_system)
    if not analysis["is_linear"]:
        offending = analysis["offending_entries"][0]
        raise DeterministicCompileError(
            "First-order system is not linear in states and inputs; "
            f"state {offending['state']!r} retains dependence on {offending['depends_on']}."
        )

    states = list(first_order_system["states"])  # type: ignore[index]
    inputs = list(first_order_system["inputs"])  # type: ignore[index]
    E = sympy.eye(len(states))
    A = analysis["A"]
    B = analysis["B"]
    offset = analysis["offset"]
    C = sympy.eye(len(states))
    D = sympy.Matrix.zeros(len(states), len(inputs))

    return {
        "form": "linear_descriptor",
        "states": states,
        "variables": states,
        "differential_states": states,
        "algebraic_variables": [],
        "inputs": inputs,
        "parameters": list(first_order_system["parameters"]),  # type: ignore[index]
        "independent_variable": first_order_system.get("independent_variable"),
        "E": matrix_to_dict(E),
        "A": matrix_to_dict(A),
        "B": matrix_to_dict(B),
        "C": matrix_to_dict(C),
        "D": matrix_to_dict(D),
        "offset": matrix_to_dict(offset),
    }


def build_descriptor_system_from_dae(
    dae_system: SemiExplicitDaeSystem,
    extraction: ExtractionResult,
) -> dict[str, object]:
    """Construct a linear descriptor system for a first-order semi-explicit DAE."""
    if any(order != 1 for order in extraction.derivative_orders.values()):
        raise DeterministicCompileError(
            "Descriptor-system extraction currently supports first-order differential states only."
        )

    differential_states = list(dae_system.differential_states)
    algebraic_variables = list(dae_system.algebraic_variables)
    variables = differential_states + algebraic_variables
    equations = list(dae_system.differential_equations) + list(dae_system.algebraic_constraints)
    if len(equations) != len(variables):
        raise DeterministicCompileError(
            "Descriptor-system extraction requires a square first-order semi-explicit DAE."
        )

    derivative_symbols = [sympy.Symbol(derivative_symbol_name(state, 1)) for state in differential_states]
    variable_symbols = [sympy.Symbol(name) for name in variables]
    input_symbols = [sympy.Symbol(name) for name in extraction.inputs]

    residual_matrix = sympy.Matrix([equation_to_residual(equation) for equation in equations])
    derivative_vector = sympy.Matrix(derivative_symbols) if derivative_symbols else sympy.Matrix.zeros(0, 0)
    variable_vector = sympy.Matrix(variable_symbols) if variable_symbols else sympy.Matrix.zeros(0, 0)
    input_vector = sympy.Matrix(input_symbols) if input_symbols else sympy.Matrix.zeros(0, 0)

    E_differential = (
        residual_matrix.jacobian(derivative_symbols)
        if derivative_symbols
        else sympy.Matrix.zeros(len(equations), 0)
    )
    A_residual = (
        residual_matrix.jacobian(variable_symbols)
        if variable_symbols
        else sympy.Matrix.zeros(len(equations), 0)
    )
    B_residual = (
        residual_matrix.jacobian(input_symbols)
        if input_symbols
        else sympy.Matrix.zeros(len(equations), 0)
    )
    offset_residual = sympy.simplify(
        residual_matrix
        - (
            E_differential * derivative_vector
            if derivative_symbols
            else sympy.Matrix.zeros(len(equations), 1)
        )
        - (A_residual * variable_vector if variable_symbols else sympy.Matrix.zeros(len(equations), 1))
        - (B_residual * input_vector if input_symbols else sympy.Matrix.zeros(len(equations), 1))
    )

    derivative_and_variable_symbols = set(derivative_symbols) | set(variable_symbols) | set(input_symbols)
    offending_entries: list[dict[str, object]] = []
    for index, entry in enumerate(offset_residual):
        offending = sorted(symbol.name for symbol in entry.free_symbols & derivative_and_variable_symbols)
        if offending:
            offending_entries.append(
                {
                    "equation_index": index,
                    "expr": sympy.sstr(entry),
                    "depends_on": offending,
                }
            )
        algebraic_derivatives = sorted(
            symbol.name
            for symbol in residual_matrix[index].free_symbols
            if symbol.name in {
                derivative_symbol_name(name, 1)
                for name in algebraic_variables
            }
        )
        if algebraic_derivatives:
            offending_entries.append(
                {
                    "equation_index": index,
                    "expr": sympy.sstr(residual_matrix[index]),
                    "depends_on": algebraic_derivatives,
                }
            )

    if offending_entries:
        offending = offending_entries[0]
        raise DeterministicCompileError(
            "Semi-explicit DAE is not linear in differential states, algebraic variables, and inputs; "
            f"equation {offending['equation_index']} retains dependence on {offending['depends_on']}."
        )

    E = sympy.Matrix.hstack(
        E_differential,
        sympy.Matrix.zeros(len(equations), len(algebraic_variables)),
    )
    A = -A_residual
    B = -B_residual
    offset = -offset_residual
    C = sympy.eye(len(variables))
    D = sympy.Matrix.zeros(len(variables), len(input_symbols))

    return {
        "form": "linear_descriptor",
        "states": variables,
        "variables": variables,
        "differential_states": differential_states,
        "algebraic_variables": algebraic_variables,
        "inputs": list(extraction.inputs),
        "parameters": list(extraction.parameters),
        "independent_variable": extraction.independent_variable,
        "E": matrix_to_dict(E),
        "A": matrix_to_dict(A),
        "B": matrix_to_dict(B),
        "C": matrix_to_dict(C),
        "D": matrix_to_dict(D),
        "offset": matrix_to_dict(offset),
    }
