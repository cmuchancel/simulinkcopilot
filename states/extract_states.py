"""Public state extraction entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Mapping

from canonicalize.algebraic_substitution import inline_algebraic_definitions
from ir.expression_nodes import EquationNode
from latex_frontend.symbols import DeterministicCompileError
from states.classify_symbols import classify_symbols
from states.rules import ExtractionResult, collect_derivative_orders, derive_state_list

if TYPE_CHECKING:
    from canonicalize.solve_for_derivatives import SolvedDerivative


@dataclass(frozen=True)
class StateExtractionAnalysis:
    """Shared symbolic-analysis output used by state extraction and pipeline compilation."""

    extraction: ExtractionResult
    resolved_equations: list[EquationNode]
    solved_derivatives: list[SolvedDerivative] | None


def analyze_state_extraction(
    equations: list[EquationNode],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> StateExtractionAnalysis:
    """Analyze equations once for state metadata and optional solved-derivative reuse."""
    resolved_equations = inline_algebraic_definitions(equations).equations
    derivative_orders = collect_derivative_orders(resolved_equations)
    states = derive_state_list(derivative_orders)

    solved_derivatives = None
    try:
        from canonicalize.solve_for_derivatives import solve_for_highest_derivatives

        solved_derivatives = solve_for_highest_derivatives(resolved_equations)
        analysis_equations = [item.equation for item in solved_derivatives]
    except DeterministicCompileError:
        analysis_equations = resolved_equations

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
    independent_variables = tuple(
        name
        for name, metadata in symbol_metadata.items()
        if metadata.role == "independent_variable"
    )
    if len(independent_variables) > 1:
        raise DeterministicCompileError("Exactly one independent variable may be declared.")

    extraction = ExtractionResult(
        states=states,
        inputs=inputs,
        parameters=parameters,
        independent_variable=independent_variables[0] if independent_variables else None,
        derivative_orders=derivative_orders,
        symbol_metadata=symbol_metadata,
    )
    return StateExtractionAnalysis(
        extraction=extraction,
        resolved_equations=resolved_equations,
        solved_derivatives=solved_derivatives,
    )


def extract_states(
    equations: list[EquationNode],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Extract states, inputs, parameters, and derivative orders deterministically."""
    return analyze_state_extraction(equations, mode=mode, symbol_config=symbol_config).extraction
