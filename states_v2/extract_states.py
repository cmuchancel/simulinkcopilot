"""Public state extraction entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ir_v2.expression_nodes import EquationNode
from latex_frontend_v2.symbols import DeterministicCompileError
from states_v2.classify_symbols import classify_symbols
from states_v2.rules import ExtractionResult, collect_derivative_orders, derive_state_list


def extract_states(
    equations: list[EquationNode],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Extract states, inputs, parameters, and derivative orders deterministically."""
    derivative_orders = collect_derivative_orders(equations)
    states = derive_state_list(derivative_orders)

    try:
        from canonicalize_v2.solve_for_derivatives import solve_for_highest_derivatives

        analysis_equations = [item.equation for item in solve_for_highest_derivatives(equations)]
    except DeterministicCompileError:
        analysis_equations = equations

    symbol_metadata = classify_symbols(
        analysis_equations,
        derivative_orders=derivative_orders,
        state_names=states,
        mode=mode,
        symbol_config=symbol_config,
    )
    inputs = tuple(
        name
        for name, metadata in symbol_metadata.items()
        if metadata.role == "input"
    )
    parameters = tuple(
        name
        for name, metadata in symbol_metadata.items()
        if metadata.role in {"parameter", "known_constant"}
    )

    return ExtractionResult(
        states=states,
        inputs=inputs,
        parameters=parameters,
        derivative_orders=derivative_orders,
        symbol_metadata=symbol_metadata,
    )
