"""Shared normalized-problem schema for all input front doors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from ir.equation_dict import equation_to_string
from ir.expression_nodes import DerivativeNode, EquationNode, ExpressionNode, NumberNode, SymbolNode
from latex_frontend.symbols import DeterministicCompileError
from states.classify_symbols import load_symbol_config
from states.rules import collect_derivative_orders


VALID_SOURCE_TYPES = {
    "latex",
    "matlab_symbolic",
    "matlab_equation_text",
    "matlab_ode_function",
}


def _expression_is_zero(node: ExpressionNode) -> bool:
    return isinstance(node, NumberNode) and node.value == 0


def _lhs_kind(node: EquationNode) -> tuple[str, str | None]:
    lhs = node.lhs
    if isinstance(lhs, DerivativeNode):
        return "derivative", lhs.base
    if _expression_is_zero(lhs):
        return "algebraic_zero", None
    if isinstance(lhs, SymbolNode):
        return "assignment", lhs.name
    return "expression", None


def normalize_equation_orientation(node: EquationNode) -> EquationNode:
    """Normalize obvious equation orientation differences deterministically."""
    lhs = node.lhs
    rhs = node.rhs
    if isinstance(rhs, DerivativeNode) and not isinstance(lhs, DerivativeNode):
        return EquationNode(lhs=rhs, rhs=lhs)
    if _expression_is_zero(rhs) and not _expression_is_zero(lhs):
        return EquationNode(lhs=rhs, rhs=lhs)
    return node


@dataclass(frozen=True)
class CanonicalEquation:
    """Canonical normalized equation wrapper above the expression-node IR."""

    lhs_kind: str
    lhs_symbol: str | None
    lhs_expression: ExpressionNode
    rhs_expression: ExpressionNode
    original_text: str | None = None
    source_index: int | None = None

    @classmethod
    def from_equation_node(
        cls,
        equation: EquationNode,
        *,
        original_text: str | None = None,
        source_index: int | None = None,
    ) -> "CanonicalEquation":
        normalized = normalize_equation_orientation(equation)
        lhs_kind, lhs_symbol = _lhs_kind(normalized)
        return cls(
            lhs_kind=lhs_kind,
            lhs_symbol=lhs_symbol,
            lhs_expression=normalized.lhs,
            rhs_expression=normalized.rhs,
            original_text=original_text,
            source_index=source_index,
        )

    def to_equation_node(self) -> EquationNode:
        return EquationNode(lhs=self.lhs_expression, rhs=self.rhs_expression)

    def to_dict(self) -> dict[str, object]:
        return {
            "lhs_kind": self.lhs_kind,
            "lhs_symbol": self.lhs_symbol,
            "equation": equation_to_string(self.to_equation_node()),
            "original_text": self.original_text,
            "source_index": self.source_index,
        }


@dataclass(frozen=True)
class NormalizedProblem:
    """Front-end-neutral normalized problem wrapper for equation-based inputs."""

    ir_version: str
    source_type: str
    source_metadata: dict[str, object]
    time_variable: str | None
    states: tuple[str, ...]
    algebraics: tuple[str, ...]
    inputs: tuple[str, ...]
    parameters: tuple[str, ...]
    equations: tuple[CanonicalEquation, ...]
    assumptions: dict[str, object] = field(default_factory=dict)
    derivative_order_info: dict[str, int] = field(default_factory=dict)
    canonical_form_metadata: dict[str, object] = field(default_factory=dict)

    def equation_nodes(self) -> list[EquationNode]:
        return [equation.to_equation_node() for equation in self.equations]

    def declared_symbol_config(self) -> dict[str, str]:
        config: dict[str, str] = {}
        for name in self.inputs:
            config[name] = "input"
        for name in self.parameters:
            config[name] = "parameter"
        if self.time_variable is not None:
            config[self.time_variable] = "independent_variable"
        return config

    def source_name(self) -> str:
        """Return a stable display/graph name for this normalized problem."""
        for key in ("name", "stem", "display_path", "path"):
            raw = self.source_metadata.get(key)
            if not isinstance(raw, str) or not raw.strip():
                continue
            if key in {"display_path", "path"}:
                return Path(raw).stem
            return raw
        return self.source_type

    def source_label(self) -> str:
        """Return a stable provenance label for reporting."""
        raw_display_path = self.source_metadata.get("display_path")
        if isinstance(raw_display_path, str) and raw_display_path.strip():
            return raw_display_path
        raw_path = self.source_metadata.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            return raw_path
        return self.source_name()

    def to_dict(self) -> dict[str, object]:
        return {
            "ir_version": self.ir_version,
            "source_type": self.source_type,
            "source_metadata": dict(self.source_metadata),
            "time_variable": self.time_variable,
            "states": list(self.states),
            "algebraics": list(self.algebraics),
            "inputs": list(self.inputs),
            "parameters": list(self.parameters),
            "equations": [equation.to_dict() for equation in self.equations],
            "assumptions": dict(self.assumptions),
            "derivative_order_info": dict(self.derivative_order_info),
            "canonical_form_metadata": dict(self.canonical_form_metadata),
        }


def build_normalized_problem(
    *,
    source_type: str,
    equations: list[EquationNode],
    original_texts: list[str] | None = None,
    source_metadata: Mapping[str, object] | None = None,
    time_variable: str | None = None,
    states: list[str] | tuple[str, ...] | None = None,
    algebraics: list[str] | tuple[str, ...] | None = None,
    inputs: list[str] | tuple[str, ...] | None = None,
    parameters: list[str] | tuple[str, ...] | None = None,
    assumptions: Mapping[str, object] | None = None,
) -> NormalizedProblem:
    """Construct a validated normalized problem from canonical equation nodes."""
    if source_type not in VALID_SOURCE_TYPES:
        raise DeterministicCompileError(
            f"Unsupported source_type {source_type!r}. Expected one of {sorted(VALID_SOURCE_TYPES)}."
        )

    states_tuple = tuple(states or ())
    algebraics_tuple = tuple(algebraics or ())
    inputs_tuple = tuple(inputs or ())
    parameters_tuple = tuple(parameters or ())
    source_metadata_dict = dict(source_metadata or {})
    assumptions_dict = dict(assumptions or {})

    duplicate_names = {
        name
        for name in {*states_tuple, *algebraics_tuple, *inputs_tuple, *parameters_tuple}
        if sum(
            name in collection
            for collection in (states_tuple, algebraics_tuple, inputs_tuple, parameters_tuple)
        )
        > 1
    }
    if duplicate_names:
        raise DeterministicCompileError(
            "NormalizedProblem symbol roles must be disjoint. Duplicates: "
            + ", ".join(sorted(duplicate_names))
        )
    if time_variable is not None and time_variable in {*states_tuple, *algebraics_tuple, *inputs_tuple, *parameters_tuple}:
        raise DeterministicCompileError(
            f"Independent variable {time_variable!r} cannot also be declared as a state/input/parameter/algebraic."
        )
    if original_texts is not None and len(original_texts) != len(equations):
        raise DeterministicCompileError(
            "NormalizedProblem original_texts must match the equation count."
        )

    canonical_equations = tuple(
        CanonicalEquation.from_equation_node(
            equation,
            original_text=None if original_texts is None else original_texts[index],
            source_index=index,
        )
        for index, equation in enumerate(equations)
    )
    derivative_orders = collect_derivative_orders([equation.to_equation_node() for equation in canonical_equations])
    canonical_form_metadata = {
        "equation_count": len(canonical_equations),
        "has_derivative_lhs": any(equation.lhs_kind == "derivative" for equation in canonical_equations),
        "has_algebraic_zero_lhs": any(equation.lhs_kind == "algebraic_zero" for equation in canonical_equations),
        "has_assignment_lhs": any(equation.lhs_kind == "assignment" for equation in canonical_equations),
        "semi_explicit_candidate": any(equation.lhs_kind == "derivative" for equation in canonical_equations)
        and any(equation.lhs_kind != "derivative" for equation in canonical_equations),
    }
    return NormalizedProblem(
        ir_version="normalized_problem_v1",
        source_type=source_type,
        source_metadata=source_metadata_dict,
        time_variable=time_variable,
        states=states_tuple,
        algebraics=algebraics_tuple,
        inputs=inputs_tuple,
        parameters=parameters_tuple,
        equations=canonical_equations,
        assumptions=assumptions_dict,
        derivative_order_info=derivative_orders,
        canonical_form_metadata=canonical_form_metadata,
    )


def merge_symbol_config(
    problem: NormalizedProblem,
    user_symbol_config: str | Path | Mapping[str, object] | None,
) -> dict[str, object] | None:
    """Merge normalized-problem role declarations with optional user symbol metadata."""
    declared = problem.declared_symbol_config()
    if user_symbol_config is None:
        return declared or None
    if isinstance(user_symbol_config, (str, Path)):
        loaded = load_symbol_config(user_symbol_config)
        merged: dict[str, object] = {
            name: metadata.role
            for name, metadata in loaded.items()
        }
    else:
        merged = dict(user_symbol_config)
    for name, role in declared.items():
        existing = merged.get(name)
        if existing is None:
            merged[name] = role
            continue
        if isinstance(existing, str):
            existing_role = existing
        elif isinstance(existing, Mapping):
            existing_role = existing.get("role")
        else:
            raise DeterministicCompileError(
                f"Configured symbol {name!r} must map to a role string or mapping."
            )
        if existing_role != role:
            raise DeterministicCompileError(
                f"Normalized problem declares symbol {name!r} as {role!r}, but symbol_config declares {existing_role!r}."
            )
    return merged


def validate_problem_against_extraction(
    problem: NormalizedProblem,
    *,
    states: tuple[str, ...],
    algebraics: tuple[str, ...],
    inputs: tuple[str, ...],
    parameters: tuple[str, ...],
    independent_variable: str | None,
) -> None:
    """Ensure explicit normalized-problem metadata agrees with downstream symbolic analysis."""
    if problem.states:
        if any(order > 1 for order in problem.derivative_order_info.values()):
            expected_state_bases = set(problem.derivative_order_info)
            if set(problem.states) != expected_state_bases:
                raise DeterministicCompileError(
                    "NormalizedProblem declared differential-state bases do not match inferred higher-order bases. "
                    f"Declared {list(problem.states)}, inferred {sorted(expected_state_bases)}."
                )
        elif set(problem.states) != set(states):
            raise DeterministicCompileError(
                "NormalizedProblem declared states do not match inferred states. "
                f"Declared {list(problem.states)}, inferred {list(states)}."
            )
    if problem.algebraics and set(problem.algebraics) != set(algebraics):
        raise DeterministicCompileError(
            "NormalizedProblem declared algebraics do not match inferred algebraic variables. "
            f"Declared {list(problem.algebraics)}, inferred {list(algebraics)}."
        )
    if problem.inputs and set(problem.inputs) != set(inputs):
        raise DeterministicCompileError(
            "NormalizedProblem declared inputs do not match inferred inputs. "
            f"Declared {list(problem.inputs)}, inferred {list(inputs)}."
        )
    if problem.parameters and set(problem.parameters) != set(parameters):
        raise DeterministicCompileError(
            "NormalizedProblem declared parameters do not match inferred parameters. "
            f"Declared {list(problem.parameters)}, inferred {list(parameters)}."
        )
    if problem.time_variable is not None and problem.time_variable != independent_variable:
        raise DeterministicCompileError(
            "NormalizedProblem declared time variable does not match inferred independent variable. "
            f"Declared {problem.time_variable!r}, inferred {independent_variable!r}."
        )
