"""Metadata-first symbol handling for the local Eqn2Sim GUI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ir.expression_nodes import DerivativeNode, EquationNode, SymbolNode, walk_expression
from latex_frontend.symbols import DeterministicCompileError
from states.rules import collect_derivative_orders, derive_state_list

GUI_SYMBOL_ROLES = (
    "state",
    "input",
    "parameter",
    "known_constant",
    "independent_variable",
)

_GUI_TO_PIPELINE_ROLE = {
    "input": "input",
    "parameter": "parameter",
    "known_constant": "known_constant",
    "independent_variable": "independent_variable",
}


@dataclass(frozen=True)
class SymbolInventoryEntry:
    name: str
    max_derivative_order: int
    appears_plain: bool
    suggested_role: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "max_derivative_order": self.max_derivative_order,
            "appears_plain": self.appears_plain,
            "suggested_role": self.suggested_role,
        }


@dataclass(frozen=True)
class GuiModelMetadata:
    latex: str
    normalized_latex: str
    equations: list[str]
    symbols: dict[str, dict[str, Any]]
    initial_conditions: dict[str, float]
    extracted_states: list[str]
    derivative_orders: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "latex": self.latex,
            "normalized_latex": self.normalized_latex,
            "equations": self.equations,
            "symbols": self.symbols,
            "initial_conditions": self.initial_conditions,
            "extracted_states": self.extracted_states,
            "derivative_orders": self.derivative_orders,
        }


def extract_symbol_inventory(equations: list[EquationNode]) -> tuple[list[SymbolInventoryEntry], tuple[str, ...], dict[str, int]]:
    """Return the user-facing symbol inventory and derived state chain."""
    derivative_orders = collect_derivative_orders(equations)
    state_chain = derive_state_list(derivative_orders)
    seen_plain: set[str] = set()
    for equation in equations:
        for node in walk_expression(equation.lhs):
            if isinstance(node, SymbolNode):
                seen_plain.add(node.name)
        for node in walk_expression(equation.rhs):
            if isinstance(node, SymbolNode):
                seen_plain.add(node.name)

    names = sorted(set(derivative_orders) | seen_plain)
    inventory = [
        SymbolInventoryEntry(
            name=name,
            max_derivative_order=derivative_orders.get(name, 0),
            appears_plain=name in seen_plain,
            suggested_role="state" if derivative_orders.get(name, 0) > 0 else "parameter",
        )
        for name in names
    ]
    return inventory, state_chain, derivative_orders


def _float_or_none(value: object) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def validate_gui_symbol_payload(
    symbol_payload: Mapping[str, Mapping[str, object]],
    derivative_orders: Mapping[str, int],
) -> dict[str, dict[str, Any]]:
    """Validate metadata submitted from the local GUI."""
    normalized: dict[str, dict[str, Any]] = {}
    for name, entry in symbol_payload.items():
        role = entry.get("role")
        if role not in GUI_SYMBOL_ROLES:
            raise DeterministicCompileError(
                f"Symbol {name!r} has unsupported GUI role {role!r}. Expected one of {GUI_SYMBOL_ROLES}."
            )
        if derivative_orders.get(name, 0) > 0 and role != "state":
            raise DeterministicCompileError(
                f"Symbol {name!r} appears with derivatives and must be marked as a state."
            )
        if role == "state" and derivative_orders.get(name, 0) <= 0:
            raise DeterministicCompileError(
                f"Symbol {name!r} was marked as a state, but no derivative of {name!r} appears in the equation set."
            )
        normalized[name] = {
            "role": role,
            "description": str(entry.get("description", "")).strip(),
            "units": str(entry.get("units", "")).strip(),
            "value": _float_or_none(entry.get("value")),
            "input_kind": str(entry.get("input_kind", "inport")).strip() or "inport",
        }
    return normalized


def gui_symbols_to_symbol_config(symbols: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """Convert GUI symbol metadata into pipeline symbol_config entries."""
    config: dict[str, str] = {}
    for name, entry in symbols.items():
        role = str(entry["role"])
        if role in _GUI_TO_PIPELINE_ROLE:
            config[name] = _GUI_TO_PIPELINE_ROLE[role]
    return config


def build_model_symbol_values_from_gui(
    symbols: Mapping[str, Mapping[str, Any]],
    initial_conditions: Mapping[str, object],
) -> dict[str, object]:
    """Convert GUI metadata into model-definition values for graph lowering."""
    parameter_values = {
        name: float(entry["value"])
        for name, entry in symbols.items()
        if entry["role"] in {"parameter", "known_constant"} and entry.get("value") is not None
    }
    input_values = {
        name: float(entry["value"])
        for name, entry in symbols.items()
        if entry["role"] == "input"
        and str(entry.get("input_kind", "inport")) == "constant"
        and entry.get("value") is not None
    }
    normalized_initials = {
        state: float(value)
        for state, value in initial_conditions.items()
        if value not in {None, ""}
    }

    return {
        "parameter_values": parameter_values,
        "input_values": input_values,
        "initial_conditions": normalized_initials,
        "input_mode": "inport",
    }


def build_runtime_override_from_gui(
    symbols: Mapping[str, Mapping[str, Any]],
    initial_conditions: Mapping[str, object],
    simulation: Mapping[str, object] | None = None,
    *,
    preview_inports_as_constant: bool = False,
) -> dict[str, object]:
    """Convert GUI metadata into the pipeline runtime-override format."""
    supported_input_kinds = {"constant"}
    if preview_inports_as_constant:
        supported_input_kinds.add("inport")
    unsupported_input_kinds = sorted(
        name
        for name, entry in symbols.items()
        if entry["role"] == "input" and str(entry.get("input_kind", "constant")) not in supported_input_kinds
    )
    if unsupported_input_kinds:
        raise DeterministicCompileError(
            "The local GUI currently supports constant-valued inputs only. "
            f"Unsupported input kinds were provided for: {', '.join(unsupported_input_kinds)}."
        )

    parameter_values = {
        name: float(entry["value"])
        for name, entry in symbols.items()
        if entry["role"] in {"parameter", "known_constant"} and entry.get("value") is not None
    }
    input_values = {
        name: float(entry["value"])
        for name, entry in symbols.items()
        if entry["role"] == "input"
        and str(entry.get("input_kind", "constant")) in supported_input_kinds
        and entry.get("value") is not None
    }
    normalized_initials = {
        state: float(value)
        for state, value in initial_conditions.items()
        if value not in {None, ""}
    }

    runtime: dict[str, object] = {
        "parameter_values": parameter_values,
        "initial_conditions": normalized_initials,
    }
    if input_values:
        runtime["input_values"] = input_values

    if simulation is not None:
        start = simulation.get("t_start")
        stop = simulation.get("t_stop")
        samples = simulation.get("sample_count")
        if start not in {None, ""} and stop not in {None, ""}:
            runtime["t_span"] = [float(start), float(stop)]
        if samples not in {None, ""}:
            runtime["sample_count"] = int(samples)
    return runtime


def save_gui_metadata(path: str | Path, metadata: GuiModelMetadata) -> Path:
    destination = Path(path)
    destination.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
    return destination
