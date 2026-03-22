"""Public state extraction entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Mapping

from canonicalize.descriptor_system import build_descriptor_system_from_dae
from canonicalize.dae_system import SemiExplicitDaeSystem, build_semi_explicit_dae_system, finalize_dae_support
from canonicalize.dae_reduction import DaeReductionResult, reduce_semi_explicit_dae
from ir.expression_nodes import EquationNode
from latex_frontend.symbols import DeterministicCompileError
from pipeline.normalized_problem import (
    NormalizedProblem,
    merge_symbol_config,
    validate_problem_against_extraction,
)
from states.classify_symbols import classify_symbols, load_symbol_config
from states.rules import ExtractionResult, collect_derivative_orders, derive_state_list

if TYPE_CHECKING:
    from canonicalize.solve_for_derivatives import SolvedDerivative


@dataclass(frozen=True)
class StateExtractionAnalysis:
    """Shared symbolic-analysis output used by state extraction and pipeline compilation."""

    extraction: ExtractionResult
    resolved_equations: list[EquationNode]
    solved_derivatives: list[SolvedDerivative] | None
    dae_reduction: DaeReductionResult
    dae_system: SemiExplicitDaeSystem
    descriptor_system: dict[str, object] | None


def analyze_state_extraction(
    equations: list[EquationNode],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> StateExtractionAnalysis:
    """Analyze equations once for state metadata and optional solved-derivative reuse."""
    configured_symbols = load_symbol_config(symbol_config)
    reduction = reduce_semi_explicit_dae(
        equations,
        protected_symbols=set(configured_symbols),
    )
    resolved_equations = reduction.equations
    derivative_orders = collect_derivative_orders(resolved_equations)
    states = derive_state_list(derivative_orders)

    solved_derivatives = None
    try:
        from canonicalize.solve_for_derivatives import solve_for_highest_derivatives

        solved_derivatives = solve_for_highest_derivatives(
            resolved_equations,
            protected_symbols=set(configured_symbols),
        )
        analysis_equations = [item.equation for item in solved_derivatives]
    except DeterministicCompileError:
        analysis_equations = resolved_equations

    symbol_metadata = classify_symbols(
        analysis_equations,
        derivative_orders=derivative_orders,
        state_names=states,
        mode=mode,
        symbol_config=symbol_config,
        reserved_symbols=set(reduction.algebraic_variables),
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
    dae_system = build_semi_explicit_dae_system(extraction, reduction)
    try:
        descriptor_system = build_descriptor_system_from_dae(dae_system, extraction)
    except DeterministicCompileError:
        descriptor_system = None
    dae_system = finalize_dae_support(dae_system, descriptor_system=descriptor_system)
    return StateExtractionAnalysis(
        extraction=extraction,
        resolved_equations=resolved_equations,
        solved_derivatives=solved_derivatives,
        dae_reduction=reduction,
        dae_system=dae_system,
        descriptor_system=descriptor_system,
    )


def analyze_normalized_problem(
    problem: NormalizedProblem,
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> StateExtractionAnalysis:
    """Analyze a normalized problem while preserving declared front-door metadata."""
    merged_symbol_config = merge_symbol_config(problem, symbol_config)
    resolved_mode = "configured" if merged_symbol_config is not None and mode == "strict" else mode
    analysis = analyze_state_extraction(
        problem.equation_nodes(),
        mode=resolved_mode,
        symbol_config=merged_symbol_config,
    )
    validate_problem_against_extraction(
        problem,
        states=analysis.extraction.states,
        algebraics=analysis.dae_system.algebraic_variables,
        inputs=analysis.extraction.inputs,
        parameters=analysis.extraction.parameters,
        independent_variable=analysis.extraction.independent_variable,
    )
    return analysis


def extract_states(
    equations: list[EquationNode],
    mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
) -> ExtractionResult:
    """Extract states, inputs, parameters, and derivative orders deterministically."""
    return analyze_state_extraction(equations, mode=mode, symbol_config=symbol_config).extraction
