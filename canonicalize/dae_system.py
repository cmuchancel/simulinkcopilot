"""Typed semi-explicit DAE system representation and support classification."""

from __future__ import annotations

from dataclasses import dataclass, replace

from canonicalize.solve_for_derivatives import solve_for_highest_derivatives
from latex_frontend.symbols import DeterministicCompileError

from canonicalize.dae_reduction import DaeReductionResult
from ir.equation_dict import equation_to_residual, equation_to_string
from ir.expression_nodes import EquationNode
from states.rules import ExtractionResult


@dataclass(frozen=True)
class DaeSupportClassification:
    """Declarative support status for a compiled DAE-like system."""

    kind: str
    route: str
    supported: bool
    python_validation_supported: bool
    simulink_lowering_supported: bool
    diagnostic: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "route": self.route,
            "supported": self.supported,
            "python_validation_supported": self.python_validation_supported,
            "simulink_lowering_supported": self.simulink_lowering_supported,
            "diagnostic": self.diagnostic,
        }


@dataclass(frozen=True)
class PreservedSemiExplicitDaeForm:
    """Explicit differential RHS plus preserved algebraic residuals."""

    differential_rhs: dict[str, EquationNode]
    algebraic_residuals: tuple[EquationNode, ...]
    algebraic_constraint_map: dict[str, EquationNode]

    def to_dict(self) -> dict[str, object]:
        return {
            "differential_rhs": {
                state: equation_to_string(equation)
                for state, equation in self.differential_rhs.items()
            },
            "algebraic_residuals": [equation_to_string(equation) for equation in self.algebraic_residuals],
            "algebraic_constraint_map": {
                name: equation_to_string(equation)
                for name, equation in self.algebraic_constraint_map.items()
            },
        }


@dataclass(frozen=True)
class SemiExplicitDaeSystem:
    """Semi-explicit DAE view of the compiled system."""

    differential_states: tuple[str, ...]
    algebraic_variables: tuple[str, ...]
    inputs: tuple[str, ...]
    parameters: tuple[str, ...]
    independent_variable: str | None
    differential_equations: tuple[EquationNode, ...]
    algebraic_constraints: tuple[EquationNode, ...]
    solved_algebraic_variables: dict[str, EquationNode]
    residual_constraints: tuple[EquationNode, ...]
    reduced_equations: tuple[EquationNode, ...]
    preserved_form: PreservedSemiExplicitDaeForm | None
    classification: DaeSupportClassification

    @property
    def reduced_to_explicit(self) -> bool:
        return not self.residual_constraints

    def to_dict(self) -> dict[str, object]:
        return {
            "differential_states": list(self.differential_states),
            "algebraic_variables": list(self.algebraic_variables),
            "inputs": list(self.inputs),
            "parameters": list(self.parameters),
            "independent_variable": self.independent_variable,
            "differential_equations": [equation_to_string(equation) for equation in self.differential_equations],
            "algebraic_constraints": [equation_to_string(equation) for equation in self.algebraic_constraints],
            "solved_algebraic_variables": {
                name: equation_to_string(equation)
                for name, equation in self.solved_algebraic_variables.items()
            },
            "residual_constraints": [equation_to_string(equation) for equation in self.residual_constraints],
            "reduced_equations": [equation_to_string(equation) for equation in self.reduced_equations],
            "reduced_to_explicit": self.reduced_to_explicit,
            "preserved_form": None if self.preserved_form is None else self.preserved_form.to_dict(),
            "classification": self.classification.to_dict(),
        }


def build_semi_explicit_dae_system(
    extraction: ExtractionResult,
    reduction: DaeReductionResult,
) -> SemiExplicitDaeSystem:
    """Build a typed semi-explicit DAE representation from symbolic analysis results."""
    preserved_form, preserved_diagnostic = _build_preserved_form(extraction, reduction)
    classification = _classify_support(reduction, preserved_form, preserved_diagnostic)
    return SemiExplicitDaeSystem(
        differential_states=tuple(extraction.states),
        algebraic_variables=tuple(reduction.algebraic_variables),
        inputs=tuple(extraction.inputs),
        parameters=tuple(extraction.parameters),
        independent_variable=extraction.independent_variable,
        differential_equations=tuple(reduction.dynamic_equations),
        algebraic_constraints=tuple(reduction.algebraic_constraints),
        solved_algebraic_variables=dict(reduction.solved_algebraic_variables),
        residual_constraints=tuple(reduction.residual_constraints),
        reduced_equations=tuple(reduction.equations),
        preserved_form=preserved_form,
        classification=classification,
    )


def finalize_dae_support(
    dae_system: SemiExplicitDaeSystem,
    *,
    descriptor_system: dict[str, object] | None,
) -> SemiExplicitDaeSystem:
    """Refine provisional preserved-DAE classification once descriptor form is known."""
    if (
        descriptor_system is None
        or dae_system.preserved_form is None
        or not dae_system.residual_constraints
        or dae_system.classification.kind == "unsupported_dae"
    ):
        return dae_system
    return replace(
        dae_system,
        classification=DaeSupportClassification(
            kind="linear_descriptor_dae",
            route="descriptor_dae",
            supported=True,
            python_validation_supported=True,
            simulink_lowering_supported=True,
            diagnostic=None,
        ),
    )


def _classify_support(
    reduction: DaeReductionResult,
    preserved_form: PreservedSemiExplicitDaeForm | None,
    preserved_diagnostic: str | None,
) -> DaeSupportClassification:
    had_algebraic_structure = bool(reduction.algebraic_constraints or reduction.solved_algebraic_variables)
    if not had_algebraic_structure:
        return DaeSupportClassification(
            kind="explicit_ode",
            route="explicit_ode",
            supported=True,
            python_validation_supported=True,
            simulink_lowering_supported=True,
        )
    if not reduction.residual_constraints:
        return DaeSupportClassification(
            kind="reducible_semi_explicit_dae",
            route="explicit_ode",
            supported=True,
            python_validation_supported=True,
            simulink_lowering_supported=True,
        )
    if preserved_form is None:
        return DaeSupportClassification(
            kind="unsupported_dae",
            route="unsupported",
            supported=False,
            python_validation_supported=False,
            simulink_lowering_supported=False,
            diagnostic=preserved_diagnostic or "Unsupported algebraic/DAE structure.",
        )
    return DaeSupportClassification(
        kind="nonlinear_preserved_semi_explicit_dae",
        route="preserved_dae",
        supported=True,
        python_validation_supported=True,
        simulink_lowering_supported=True,
        diagnostic=None,
    )


def _build_preserved_form(
    extraction: ExtractionResult,
    reduction: DaeReductionResult,
) -> tuple[PreservedSemiExplicitDaeForm | None, str | None]:
    if not reduction.residual_constraints:
        return None, None
    if any(order != 1 for order in extraction.derivative_orders.values()):
        return None, "Preserved-constraint DAE support currently requires first-order differential states."

    protected_symbols = {
        *extraction.inputs,
        *extraction.parameters,
    }
    if extraction.independent_variable is not None:
        protected_symbols.add(extraction.independent_variable)

    try:
        solved_dynamic = solve_for_highest_derivatives(
            list(reduction.dynamic_equations),
            protected_symbols=protected_symbols,
        )
    except DeterministicCompileError as exc:
        return None, (
            "Differential equations are not explicit in the supported semi-explicit form: "
            + str(exc)
        )

    differential_rhs = {
        item.base: item.equation
        for item in solved_dynamic
    }
    expected_states = set(extraction.states)
    if set(differential_rhs) != expected_states:
        return None, "Differential equations do not isolate exactly one derivative for each differential state."

    constraint_map = _assign_algebraic_constraints(
        reduction.algebraic_variables,
        reduction.residual_constraints,
    )
    if constraint_map is None:
        return None, (
            "Algebraic subsystem is structurally singular, non-square, or ambiguously assigned to algebraic variables."
        )

    return (
        PreservedSemiExplicitDaeForm(
            differential_rhs=differential_rhs,
            algebraic_residuals=tuple(reduction.residual_constraints),
            algebraic_constraint_map=constraint_map,
        ),
        None,
    )


def _assign_algebraic_constraints(
    algebraic_variables: tuple[str, ...],
    residual_constraints: tuple[EquationNode, ...],
) -> dict[str, EquationNode] | None:
    if not algebraic_variables and not residual_constraints:
        return {}
    if len(algebraic_variables) != len(residual_constraints):
        return None

    adjacency: dict[int, list[int]] = {}
    variable_names = list(algebraic_variables)
    for row_index, equation in enumerate(residual_constraints):
        free_symbol_names = {
            symbol.name
            for symbol in equation_to_residual(equation).free_symbols
        }
        adjacency[row_index] = [
            column_index
            for column_index, variable_name in enumerate(variable_names)
            if variable_name in free_symbol_names
        ]
        if not adjacency[row_index]:
            return None

    matches: dict[int, int] = {}

    def assign(row_index: int, seen: set[int]) -> bool:
        for column_index in adjacency[row_index]:
            if column_index in seen:
                continue
            seen.add(column_index)
            current_row = matches.get(column_index)
            if current_row is None or assign(current_row, seen):
                matches[column_index] = row_index
                return True
        return False

    for row_index in range(len(residual_constraints)):
        if not assign(row_index, set()):
            return None

    return {
        variable_names[column_index]: residual_constraints[row_index]
        for column_index, row_index in matches.items()
    }
