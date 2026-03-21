"""Typed semi-explicit DAE system representation."""

from __future__ import annotations

from dataclasses import dataclass

from canonicalize.dae_reduction import DaeReductionResult
from ir.equation_dict import equation_to_string
from ir.expression_nodes import EquationNode
from states.rules import ExtractionResult


@dataclass(frozen=True)
class SemiExplicitDaeSystem:
    """Semi-explicit DAE view of the compiled system."""

    differential_states: tuple[str, ...]
    algebraic_variables: tuple[str, ...]
    differential_equations: tuple[EquationNode, ...]
    algebraic_constraints: tuple[EquationNode, ...]
    solved_algebraic_variables: dict[str, EquationNode]
    residual_constraints: tuple[EquationNode, ...]
    reduced_equations: tuple[EquationNode, ...]

    @property
    def reduced_to_explicit(self) -> bool:
        return not self.residual_constraints

    def to_dict(self) -> dict[str, object]:
        return {
            "differential_states": list(self.differential_states),
            "algebraic_variables": list(self.algebraic_variables),
            "differential_equations": [equation_to_string(equation) for equation in self.differential_equations],
            "algebraic_constraints": [equation_to_string(equation) for equation in self.algebraic_constraints],
            "solved_algebraic_variables": {
                name: equation_to_string(equation)
                for name, equation in self.solved_algebraic_variables.items()
            },
            "residual_constraints": [equation_to_string(equation) for equation in self.residual_constraints],
            "reduced_equations": [equation_to_string(equation) for equation in self.reduced_equations],
            "reduced_to_explicit": self.reduced_to_explicit,
        }


def build_semi_explicit_dae_system(
    extraction: ExtractionResult,
    reduction: DaeReductionResult,
) -> SemiExplicitDaeSystem:
    """Build a typed semi-explicit DAE representation from symbolic analysis results."""
    return SemiExplicitDaeSystem(
        differential_states=tuple(extraction.states),
        algebraic_variables=tuple(reduction.algebraic_variables),
        differential_equations=tuple(reduction.dynamic_equations),
        algebraic_constraints=tuple(reduction.algebraic_constraints),
        solved_algebraic_variables=dict(reduction.solved_algebraic_variables),
        residual_constraints=tuple(reduction.residual_constraints),
        reduced_equations=tuple(reduction.equations),
    )
