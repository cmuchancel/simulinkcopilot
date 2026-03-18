"""Deterministic lowering from validated graphs to Simulink-ready dictionaries."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from backend.block_library import BLOCK_LIBRARY
from backend.simulink_dict import BackendSimulinkModelDict, validate_simulink_model_dict
from ir.graph_validate import validate_graph_dict
from latex_frontend.symbols import (
    DeterministicCompileError,
    DIRECT_SIMULINK_MATH_FUNCTIONS,
    DIRECT_SIMULINK_TRIG_FUNCTIONS,
    RECIPROCAL_FUNCTION_BASES,
)
from simulink.utils import sanitize_block_name


def _numeric_string(value: float | int) -> str:
    if float(value).is_integer():
        return str(int(round(float(value))))
    return repr(float(value))


def _sanitize_for_id(name: str) -> str:
    return sanitize_block_name(name)


def _safe_reciprocal(value: float) -> float:
    if math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-15):
        raise DeterministicCompileError("Reciprocal function encountered a zero denominator during constant folding.")
    return 1.0 / value


@dataclass
class GraphToSimulinkLowerer:
    graph: dict[str, object]
    model_name: str
    symbol_values: dict[str, float] = field(default_factory=dict)
    input_signals: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    input_mode: str = "constant"
    blocks: dict[str, dict[str, object]] = field(default_factory=dict)
    connections: list[tuple[str, str, str, str]] = field(default_factory=list)
    node_source_cache: dict[str, tuple[str, str]] = field(default_factory=dict)
    numeric_cache: dict[str, float | None] = field(default_factory=dict)
    workspace_variables: dict[str, object] = field(default_factory=dict)
    inport_counter: int = 0

    def __post_init__(self) -> None:
        self.graph = validate_graph_dict(self.graph)
        self.node_map = {node["id"]: node for node in self.graph["nodes"]}  # type: ignore[index]
        self.state_chain_map = {
            entry["state"]: entry
            for entry in self.graph.get("state_chains", [])  # type: ignore[index]
        }

    def numeric_value(self, node_id: str) -> float | None:
        """Return a numeric value if the node subtree is compile-time evaluable."""
        if node_id in self.numeric_cache:
            return self.numeric_cache[node_id]

        node = self.node_map[node_id]
        op = node["op"]
        value: float | None
        if op == "constant":
            value = float(node["value"])
        elif op == "symbol_input":
            symbol_name = node["name"]
            value = float(self.symbol_values[symbol_name]) if symbol_name in self.symbol_values else None
        elif op in {"state_signal", "integrator"}:
            value = None
        else:
            child_values = [self.numeric_value(child_id) for child_id in node.get("inputs", [])]
            if any(child is None for child in child_values):
                value = None
            elif op in {"add", "sum"}:
                value = float(sum(child_values))
            elif op in {"mul", "gain"}:
                value = float(np.prod(child_values, dtype=float))
            elif op == "div":
                value = float(child_values[0] / child_values[1])
            elif op == "negate":
                value = float(-child_values[0])
            elif op == "pow":
                value = float(child_values[0] ** child_values[1])
            elif op == "sin":
                value = float(math.sin(child_values[0]))
            elif op == "cos":
                value = float(math.cos(child_values[0]))
            elif op == "tan":
                value = float(math.tan(child_values[0]))
            elif op == "sec":
                value = float(_safe_reciprocal(math.cos(child_values[0])))
            elif op == "csc":
                value = float(_safe_reciprocal(math.sin(child_values[0])))
            elif op == "cot":
                value = float(_safe_reciprocal(math.tan(child_values[0])))
            elif op == "asin":
                value = float(math.asin(child_values[0]))
            elif op == "acos":
                value = float(math.acos(child_values[0]))
            elif op == "atan":
                value = float(math.atan(child_values[0]))
            elif op == "sinh":
                value = float(math.sinh(child_values[0]))
            elif op == "cosh":
                value = float(math.cosh(child_values[0]))
            elif op == "tanh":
                value = float(math.tanh(child_values[0]))
            elif op == "sech":
                value = float(_safe_reciprocal(math.cosh(child_values[0])))
            elif op == "csch":
                value = float(_safe_reciprocal(math.sinh(child_values[0])))
            elif op == "coth":
                value = float(_safe_reciprocal(math.tanh(child_values[0])))
            elif op == "asinh":
                value = float(math.asinh(child_values[0]))
            elif op == "acosh":
                value = float(math.acosh(child_values[0]))
            elif op == "atanh":
                value = float(math.atanh(child_values[0]))
            elif op == "exp":
                value = float(math.exp(child_values[0]))
            elif op == "log":
                value = float(math.log(child_values[0]))
            else:
                value = None

        self.numeric_cache[node_id] = value
        return value

    def add_block(self, block_name: str, block_type: str, params: dict[str, object] | None = None) -> str:
        """Add a block spec once."""
        sanitized = _sanitize_for_id(block_name)
        if sanitized not in self.blocks:
            self.blocks[sanitized] = {
                "type": block_type,
                "lib_path": BLOCK_LIBRARY[block_type]["path"],
                "params": dict(params or {}),
            }
        return sanitized

    def add_connection(self, src: tuple[str, str], dst_block: str, dst_port: int) -> None:
        """Append a deterministic connection."""
        self.connections.append((src[0], src[1], dst_block, str(dst_port)))

    def materialize(self, node_id: str) -> tuple[str, str]:
        """Materialize a graph node into a Simulink block output."""
        if node_id in self.node_source_cache:
            return self.node_source_cache[node_id]

        node = self.node_map[node_id]
        op = node["op"]
        numeric_value = self.numeric_value(node_id)

        if op == "state_signal":
            source = self.materialize(node["inputs"][0])
            self.node_source_cache[node_id] = source
            return source

        if op != "integrator" and numeric_value is not None:
            block_name = self.add_block(f"const_{node_id}", "Constant", {"Value": _numeric_string(numeric_value)})
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            return source

        if op == "constant":
            block_name = self.add_block(f"const_{node_id}", "Constant", {"Value": _numeric_string(node["value"])})
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            return source

        if op == "symbol_input":
            symbol_name = str(node["name"])
            if symbol_name in self.symbol_values:
                block_name = self.add_block(
                    f"symbol_{symbol_name}",
                    "Constant",
                    {"Value": _numeric_string(self.symbol_values[symbol_name])},
                )
            elif self.input_mode == "inport":
                self.inport_counter += 1
                block_name = self.add_block(
                    f"input_{symbol_name}",
                    "Inport",
                    {"Port": self.inport_counter},
                )
            elif symbol_name in self.input_signals:
                workspace_name = f"{self.model_name}_{_sanitize_for_id(symbol_name)}_input"
                series = self.input_signals[symbol_name]
                times = list(series["time"])
                values = list(series["values"])
                if len(times) != len(values):
                    raise DeterministicCompileError(
                        f"Input signal {symbol_name!r} has mismatched time/value lengths."
                    )
                self.workspace_variables[workspace_name] = [
                    [float(time), float(value)]
                    for time, value in zip(times, values)
                ]
                block_name = self.add_block(
                    f"input_{symbol_name}",
                    "FromWorkspace",
                    {"VariableName": workspace_name},
                )
            else:
                raise DeterministicCompileError(
                    f"No numeric value or input signal provided for symbol input {symbol_name!r}."
                )
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            return source

        if op == "integrator":
            params: dict[str, object] = {}
            state_name = str(node.get("state", ""))
            if state_name in self.initial_conditions:
                params["InitialCondition"] = _numeric_string(self.initial_conditions[state_name])
            block_name = self.add_block(f"int_{node_id}", "Integrator", params)
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            rhs_source = self.materialize(node["inputs"][0])
            self.add_connection(rhs_source, block_name, 1)
            return source

        if op in {"add", "sum"}:
            block_name = self.add_block(
                f"sum_{node_id}",
                "Sum",
                {"Inputs": "+" * len(node["inputs"])},
            )
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            for index, child_id in enumerate(node["inputs"], start=1):
                self.add_connection(self.materialize(child_id), block_name, index)
            return source

        if op in {"mul", "gain"}:
            child_values = [self.numeric_value(child_id) for child_id in node["inputs"]]
            dynamic_children = [child_id for child_id, value in zip(node["inputs"], child_values) if value is None]
            if len(node["inputs"]) == 2 and len(dynamic_children) == 1:
                gain_value = next(value for value in child_values if value is not None)
                block_name = self.add_block(
                    f"gain_{node_id}",
                    "Gain",
                    {"Gain": _numeric_string(gain_value)},
                )
                source = (block_name, "1")
                self.node_source_cache[node_id] = source
                self.add_connection(self.materialize(dynamic_children[0]), block_name, 1)
                return source

            block_name = self.add_block(
                f"prod_{node_id}",
                "Product",
                {"Inputs": "*" * len(node["inputs"])},
            )
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            for index, child_id in enumerate(node["inputs"], start=1):
                self.add_connection(self.materialize(child_id), block_name, index)
            return source

        if op == "div":
            numerator_id, denominator_id = node["inputs"]
            denominator_value = self.numeric_value(denominator_id)
            if denominator_value is not None and self.numeric_value(numerator_id) is None:
                block_name = self.add_block(
                    f"gain_{node_id}",
                    "Gain",
                    {"Gain": _numeric_string(1.0 / denominator_value)},
                )
                source = (block_name, "1")
                self.node_source_cache[node_id] = source
                self.add_connection(self.materialize(numerator_id), block_name, 1)
                return source

            block_name = self.add_block(f"div_{node_id}", "Divide")
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            self.add_connection(self.materialize(numerator_id), block_name, 1)
            self.add_connection(self.materialize(denominator_id), block_name, 2)
            return source

        if op == "negate":
            block_name = self.add_block(f"neg_{node_id}", "Gain", {"Gain": "-1"})
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            self.add_connection(self.materialize(node["inputs"][0]), block_name, 1)
            return source

        if op in DIRECT_SIMULINK_TRIG_FUNCTIONS:
            block_name = self.add_block(
                f"{op}_{node_id}",
                "TrigonometricFunction",
                {"Operator": op},
            )
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            self.add_connection(self.materialize(node["inputs"][0]), block_name, 1)
            return source

        if op in RECIPROCAL_FUNCTION_BASES:
            base_op = RECIPROCAL_FUNCTION_BASES[op]
            trig_block = self.add_block(
                f"{base_op}_{node_id}",
                "TrigonometricFunction",
                {"Operator": base_op},
            )
            self.add_connection(self.materialize(node["inputs"][0]), trig_block, 1)
            one_block = self.add_block("const_reciprocal_one", "Constant", {"Value": "1"})
            div_block = self.add_block(f"{op}_{node_id}", "Divide")
            source = (div_block, "1")
            self.node_source_cache[node_id] = source
            self.add_connection((one_block, "1"), div_block, 1)
            self.add_connection((trig_block, "1"), div_block, 2)
            return source

        if op in DIRECT_SIMULINK_MATH_FUNCTIONS:
            block_name = self.add_block(
                f"{op}_{node_id}",
                "MathFunction",
                {"Operator": op},
            )
            source = (block_name, "1")
            self.node_source_cache[node_id] = source
            self.add_connection(self.materialize(node["inputs"][0]), block_name, 1)
            return source

        if op == "pow":
            base_id, exponent_id = node["inputs"]
            exponent_value = self.numeric_value(exponent_id)
            if exponent_value is None:
                raise DeterministicCompileError(f"Power node {node_id!r} requires a numeric exponent.")
            rounded = int(round(exponent_value))
            if math.isclose(exponent_value, 0.0, rel_tol=0.0, abs_tol=1e-12):
                block_name = self.add_block(f"const_{node_id}", "Constant", {"Value": "1"})
                source = (block_name, "1")
                self.node_source_cache[node_id] = source
                return source
            if math.isclose(exponent_value, 1.0, rel_tol=0.0, abs_tol=1e-12):
                source = self.materialize(base_id)
                self.node_source_cache[node_id] = source
                return source
            if math.isclose(exponent_value, rounded, rel_tol=0.0, abs_tol=1e-12):
                base_source = self.materialize(base_id)
                power_source: tuple[str, str]
                magnitude = abs(rounded)
                if magnitude == 1:
                    power_source = base_source
                else:
                    block_name = self.add_block(
                        f"prod_{node_id}",
                        "Product",
                        {"Inputs": "*" * magnitude},
                    )
                    power_source = (block_name, "1")
                    for index in range(1, magnitude + 1):
                        self.add_connection(base_source, block_name, index)
                if rounded > 0:
                    self.node_source_cache[node_id] = power_source
                    return power_source
                one_block = self.add_block("const_reciprocal_one", "Constant", {"Value": "1"})
                div_block = self.add_block(f"pow_recip_{node_id}", "Divide")
                source = (div_block, "1")
                self.node_source_cache[node_id] = source
                self.add_connection((one_block, "1"), div_block, 1)
                self.add_connection(power_source, div_block, 2)
                return source

            log_block = self.add_block(f"log_{node_id}", "MathFunction", {"Operator": "log"})
            gain_block = self.add_block(f"pow_gain_{node_id}", "Gain", {"Gain": _numeric_string(exponent_value)})
            exp_block = self.add_block(f"exp_{node_id}", "MathFunction", {"Operator": "exp"})
            source = (exp_block, "1")
            self.node_source_cache[node_id] = source
            base_source = self.materialize(base_id)
            self.add_connection(base_source, log_block, 1)
            self.add_connection((log_block, "1"), gain_block, 1)
            self.add_connection((gain_block, "1"), exp_block, 1)
            return source

        raise DeterministicCompileError(f"Unsupported graph op {op!r} in Simulink lowering.")

    def lower(self, state_names: list[str] | None = None, model_params: dict[str, object] | None = None) -> BackendSimulinkModelDict:
        """Lower the graph to a backend Simulink dictionary."""
        output_states = state_names or list(self.state_chain_map)
        outputs: list[dict[str, str]] = []

        for index, state in enumerate(output_states, start=1):
            if state not in self.state_chain_map:
                raise DeterministicCompileError(f"Requested Simulink output {state!r} not found in graph state chains.")
            signal_id = self.state_chain_map[state]["signal"]
            signal_source = self.materialize(signal_id)
            out_block = self.add_block(
                f"out_{state}",
                "Outport",
                {"Port": index},
            )
            self.add_connection(signal_source, out_block, 1)
            outputs.append({"name": state, "block": out_block, "port": "1"})

        return validate_simulink_model_dict(
            {
                "name": self.model_name,
                "blocks": self.blocks,
                "connections": self.connections,
                "outputs": outputs,
                "model_params": dict(model_params or {}),
                "workspace_variables": dict(self.workspace_variables),
                "metadata": {
                    "graph_name": self.graph["name"],
                    "state_names": list(output_states),
                },
            }
        )


def graph_to_simulink_model(
    graph: dict[str, object],
    *,
    name: str | None = None,
    state_names: list[str] | None = None,
    parameter_values: dict[str, float] | None = None,
    input_values: dict[str, float] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    initial_conditions: dict[str, float] | None = None,
    model_params: dict[str, object] | None = None,
    input_mode: str = "constant",
) -> BackendSimulinkModelDict:
    """Lower a validated graph dictionary into a Simulink-ready model dictionary."""
    symbol_values = dict(parameter_values or {})
    symbol_values.update(input_values or {})
    lowerer = GraphToSimulinkLowerer(
        graph=graph,
        model_name=name or f"{graph['name']}_simulink",
        symbol_values=symbol_values,
        input_signals=dict(input_signals or {}),
        initial_conditions=dict(initial_conditions or {}),
        input_mode=input_mode,
    )
    return lowerer.lower(state_names=state_names, model_params=model_params)
