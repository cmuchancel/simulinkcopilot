"""Shared symbolic compilation stages for ODE-to-Simulink backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from canonicalize.first_order import build_first_order_system
from canonicalize.linearity_check import analyze_first_order_linearity
from canonicalize.nonlinear_forms import build_explicit_system_form
from canonicalize.solve_for_derivatives import SolvedDerivative, solve_for_highest_derivatives
from canonicalize.state_space import build_state_space_system
from ir.equation_dict import equation_to_dict
from ir.expression_nodes import EquationNode
from ir.graph_lowering import lower_first_order_system_graph
from ir.graph_validate import validate_graph_dict
from latex_frontend.symbols import DeterministicCompileError
from states.extract_states import ExtractionResult, analyze_state_extraction


class SymbolicCompilationStageError(DeterministicCompileError):
    """Wrap a symbolic compilation failure with the stage that produced it."""

    def __init__(
        self,
        stage: str,
        message: str,
        *,
        completed_stages: tuple[str, ...] = (),
        linearity: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.completed_stages = completed_stages
        self.linearity = linearity


@dataclass(frozen=True)
class SymbolicCompilationResult:
    """Shared symbolic artifacts for the ODE-to-Simulink compile path."""

    equations: list[EquationNode]
    equation_dicts: list[dict[str, object]]
    extraction: ExtractionResult
    resolved_equations: list[EquationNode]
    solved_derivatives: list[SolvedDerivative]
    first_order: dict[str, object]
    explicit_form: dict[str, object]
    linearity: dict[str, object]
    state_space: dict[str, object] | None
    graph: dict[str, object]
    validated_graph: dict[str, object] | None


def compile_symbolic_system(
    equations: list[EquationNode],
    *,
    graph_name: str,
    classification_mode: str = "strict",
    symbol_config: str | Path | Mapping[str, object] | None = None,
    validate_graph: bool = False,
) -> SymbolicCompilationResult:
    """Compile parsed equations through the shared symbolic backend stages."""
    equation_dicts = [equation_to_dict(equation) for equation in equations]

    try:
        analysis = analyze_state_extraction(
            equations,
            mode=classification_mode,
            symbol_config=symbol_config,
        )
    except Exception as exc:
        raise SymbolicCompilationStageError("state_extraction", str(exc)) from exc

    solved_derivatives = analysis.solved_derivatives
    if solved_derivatives is None:
        try:
            solved_derivatives = solve_for_highest_derivatives(analysis.resolved_equations)
        except Exception as exc:
            raise SymbolicCompilationStageError(
                "solve",
                str(exc),
                completed_stages=("state_extraction",),
            ) from exc

    try:
        first_order = build_first_order_system(
            analysis.resolved_equations,
            extraction=analysis.extraction,
            solved_derivatives=solved_derivatives,
        )
    except Exception as exc:
        raise SymbolicCompilationStageError(
            "first_order",
            str(exc),
            completed_stages=("state_extraction", "solve"),
        ) from exc

    explicit_form = build_explicit_system_form(first_order)

    try:
        linearity = analyze_first_order_linearity(first_order)
        state_space = build_state_space_system(first_order) if linearity["is_linear"] else None
    except Exception as exc:
        raise SymbolicCompilationStageError(
            "state_space",
            str(exc),
            completed_stages=("state_extraction", "solve", "first_order"),
        ) from exc

    try:
        graph = lower_first_order_system_graph(first_order, name=graph_name)
    except Exception as exc:
        raise SymbolicCompilationStageError(
            "graph_lowering",
            str(exc),
            completed_stages=("state_extraction", "solve", "first_order", "state_space"),
            linearity=linearity,
        ) from exc

    validated_graph = None
    if validate_graph:
        try:
            validated_graph = validate_graph_dict(graph)
        except Exception as exc:
            raise SymbolicCompilationStageError(
                "graph_validation",
                str(exc),
                completed_stages=("state_extraction", "solve", "first_order", "state_space", "graph_lowering"),
                linearity=linearity,
            ) from exc

    return SymbolicCompilationResult(
        equations=equations,
        equation_dicts=equation_dicts,
        extraction=analysis.extraction,
        resolved_equations=analysis.resolved_equations,
        solved_derivatives=solved_derivatives,
        first_order=first_order,
        explicit_form=explicit_form,
        linearity=linearity,
        state_space=state_space,
        graph=graph,
        validated_graph=validated_graph,
    )
