"""Hierarchical graph-to-Simulink lowering with deterministic layout and traceability."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from backend.block_library import BLOCK_LIBRARY
from backend.layout import annotate_integrator_orders, apply_deterministic_layout
from backend.simulink_dict import ROOT_SYSTEM, SUBSYSTEM_BLOCK, BackendSimulinkModelDict, validate_simulink_model_dict
from backend.traceability import build_node_expressions, state_base_name, state_order
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


def _group_key_for_state(state: str) -> str:
    return state_base_name(state)


@dataclass
class GraphToSimulinkLowerer:
    graph: dict[str, object]
    model_name: str
    symbol_values: dict[str, float] = field(default_factory=dict)
    input_signals: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    input_mode: str = "constant"
    blocks: dict[str, dict[str, object]] = field(default_factory=dict)
    connections: list[dict[str, object]] = field(default_factory=list)
    local_source_cache: dict[str, tuple[str, str]] = field(default_factory=dict)
    import_cache: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    export_cache: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    numeric_cache: dict[str, float | None] = field(default_factory=dict)
    workspace_variables: dict[str, object] = field(default_factory=dict)
    inport_counters: dict[str, int] = field(default_factory=dict)
    outport_counters: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.graph = validate_graph_dict(self.graph)
        self.node_map = {node["id"]: node for node in self.graph["nodes"]}  # type: ignore[index]
        self.state_chain_map = {
            entry["state"]: entry
            for entry in self.graph.get("state_chains", [])  # type: ignore[index]
        }
        self.node_expressions = build_node_expressions(self.graph)
        self.state_groups = self._build_state_groups()
        self.node_groups = self._build_node_groups()
        self.node_owners = self._build_node_owners()
        self.node_layers = {
            node_id: self._graph_layer(node_id, set())
            for node_id, node in self.node_map.items()
            if node["op"] not in {"state_signal", "integrator"}
        }
        for group in self.state_groups:
            subsystem_id = self._subsystem_block_id(group)
            self.add_block(
                subsystem_id,
                "Subsystem",
                system=ROOT_SYSTEM,
                name=f"{group}_dynamics",
                lib_path=SUBSYSTEM_BLOCK,
                metadata={
                    "layout_role": "subsystem",
                    "group": group,
                    "inport_count": 0,
                    "outport_count": 0,
                },
            )

    def _build_state_groups(self) -> list[str]:
        groups = {_group_key_for_state(state) for state in self.state_chain_map}
        return sorted(groups)

    def _subsystem_block_id(self, group: str) -> str:
        return f"subsystem_{_sanitize_for_id(group)}"

    def _state_owner(self, state: str) -> str:
        return self._subsystem_block_id(_group_key_for_state(state))

    def _mark_group_dependency(self, node_id: str, group: str, seen: set[tuple[str, str]]) -> None:
        marker = (node_id, group)
        if marker in seen:
            return
        seen.add(marker)
        self.node_groups.setdefault(node_id, set()).add(group)
        if self.node_map[node_id]["op"] in {"state_signal", "constant", "symbol_input"}:
            return
        for child_id in self.node_map[node_id].get("inputs", []):
            self._mark_group_dependency(child_id, group, seen)

    def _build_node_groups(self) -> dict[str, set[str]]:
        groups: dict[str, set[str]] = {}
        for state, chain in self.state_chain_map.items():
            self.node_groups = groups
            self._mark_group_dependency(chain["rhs"], _group_key_for_state(state), set())
        return groups

    def _build_node_owners(self) -> dict[str, str]:
        owners: dict[str, str] = {}
        for node_id, node in self.node_map.items():
            op = node["op"]
            if op in {"constant", "symbol_input"}:
                owners[node_id] = ROOT_SYSTEM
            elif op in {"integrator", "state_signal"}:
                owners[node_id] = self._state_owner(str(node["state"]))
            else:
                groups = sorted(self.node_groups.get(node_id, set()))
                owners[node_id] = self._subsystem_block_id(groups[0]) if len(groups) == 1 else ROOT_SYSTEM
        return owners

    def _graph_layer(self, node_id: str, active: set[str]) -> int:
        if node_id in active:
            return 0
        node = self.node_map[node_id]
        op = node["op"]
        if op in {"constant", "symbol_input", "state_signal", "integrator"}:
            return 0
        active.add(node_id)
        child_layers = [self._graph_layer(child_id, active) for child_id in node.get("inputs", [])]
        active.remove(node_id)
        return (max(child_layers) + 1) if child_layers else 0

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
            symbol_name = str(node["name"])
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

    def add_block(
        self,
        block_id: str,
        block_type: str,
        *,
        system: str,
        name: str | None = None,
        params: dict[str, object] | None = None,
        lib_path: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        if block_id not in self.blocks:
            self.blocks[block_id] = {
                "type": block_type,
                "lib_path": lib_path or BLOCK_LIBRARY[block_type]["path"],
                "params": dict(params or {}),
                "system": system,
                "name": name or block_id,
                "metadata": dict(metadata or {}),
            }
        return block_id

    def add_connection(
        self,
        system: str,
        src: tuple[str, str],
        dst_block: str,
        dst_port: int,
        *,
        label: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.connections.append(
            {
                "system": system,
                "src_block": src[0],
                "src_port": src[1],
                "dst_block": dst_block,
                "dst_port": str(dst_port),
                "label": label,
                "metadata": dict(metadata or {}),
            }
        )

    def _subsystem_port_count(self, subsystem_id: str, key: str) -> int:
        metadata = self.blocks[subsystem_id]["metadata"]
        metadata[key] = int(metadata.get(key, 0)) + 1
        return int(metadata[key])

    def _import_from_root(self, node_id: str, consumer_system: str, root_ref: tuple[str, str]) -> tuple[str, str]:
        cache_key = (consumer_system, node_id)
        if cache_key in self.import_cache:
            return self.import_cache[cache_key]

        port = self._subsystem_port_count(consumer_system, "inport_count")
        node = self.node_map[node_id]
        local_name = (
            f"in_{node['state']}" if node["op"] == "state_signal" else f"in_{_sanitize_for_id(node_id)}"
        )
        inport_id = f"{consumer_system}__in_{_sanitize_for_id(node_id)}"
        self.add_block(
            inport_id,
            "Inport",
            system=consumer_system,
            name=local_name,
            params={"Port": port},
            metadata={
                "layout_role": "inport",
                "trace_expression": self.node_expressions[node_id],
            },
        )
        source = (inport_id, "1")
        self.import_cache[cache_key] = source
        self.add_connection(
            ROOT_SYSTEM,
            root_ref,
            consumer_system,
            port,
            label=self.node_expressions[node_id],
        )
        return source

    def _export_to_root(self, node_id: str, owner_system: str) -> tuple[str, str]:
        cache_key = (owner_system, node_id)
        if cache_key in self.export_cache:
            return self.export_cache[cache_key]

        port = self._subsystem_port_count(owner_system, "outport_count")
        node = self.node_map[node_id]
        local_name = (
            f"out_{node['state']}" if node["op"] == "state_signal" else f"out_{_sanitize_for_id(node_id)}"
        )
        outport_id = f"{owner_system}__out_{_sanitize_for_id(node_id)}"
        self.add_block(
            outport_id,
            "Outport",
            system=owner_system,
            name=local_name,
            params={"Port": port},
            metadata={
                "layout_role": "outport",
                "trace_expression": self.node_expressions[node_id],
            },
        )
        root_ref = (owner_system, str(port))
        self.export_cache[cache_key] = root_ref
        source = self.materialize_owned(node_id)
        self.add_connection(
            owner_system,
            source,
            outport_id,
            1,
            label=self.node_expressions[node_id],
        )
        return root_ref

    def resolve_for_system(self, node_id: str, consumer_system: str) -> tuple[str, str]:
        owner = self.node_owners[node_id]
        if owner == consumer_system:
            return self.materialize_owned(node_id)
        if owner == ROOT_SYSTEM:
            root_ref = self.materialize_owned(node_id)
            return root_ref if consumer_system == ROOT_SYSTEM else self._import_from_root(node_id, consumer_system, root_ref)
        root_ref = self._export_to_root(node_id, owner)
        return root_ref if consumer_system == ROOT_SYSTEM else self._import_from_root(node_id, consumer_system, root_ref)

    def materialize_owned(self, node_id: str) -> tuple[str, str]:
        if node_id in self.local_source_cache:
            return self.local_source_cache[node_id]

        node = self.node_map[node_id]
        op = node["op"]
        owner = self.node_owners[node_id]
        numeric_value = self.numeric_value(node_id)

        if op == "state_signal":
            source = self.materialize_owned(node["inputs"][0])
            self.local_source_cache[node_id] = source
            return source

        if op == "constant":
            block_id = self.add_block(
                f"const_{node_id}",
                "Constant",
                system=owner,
                name=f"const_{_sanitize_for_id(node_id)}",
                params={"Value": _numeric_string(node["value"])},
                metadata={
                    "layout_role": "source" if owner == ROOT_SYSTEM else "compute",
                    "trace_expression": self.node_expressions[node_id],
                    "layer_hint": 0,
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            return source

        if op == "symbol_input":
            symbol_name = str(node["name"])
            metadata = {
                "layout_role": "source",
                "trace_expression": self.node_expressions[node_id],
                "layer_hint": 0,
            }
            if symbol_name in self.symbol_values:
                block_id = self.add_block(
                    f"symbol_{_sanitize_for_id(symbol_name)}",
                    "Constant",
                    system=ROOT_SYSTEM,
                    name=f"symbol_{symbol_name}",
                    params={"Value": _numeric_string(self.symbol_values[symbol_name])},
                    metadata=metadata,
                )
            elif self.input_mode == "inport":
                port = self.inport_counters.get(ROOT_SYSTEM, 0) + 1
                self.inport_counters[ROOT_SYSTEM] = port
                block_id = self.add_block(
                    f"input_{_sanitize_for_id(symbol_name)}",
                    "Inport",
                    system=ROOT_SYSTEM,
                    name=f"input_{symbol_name}",
                    params={"Port": port},
                    metadata=metadata,
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
                block_id = self.add_block(
                    f"input_{_sanitize_for_id(symbol_name)}",
                    "FromWorkspace",
                    system=ROOT_SYSTEM,
                    name=f"input_{symbol_name}",
                    params={"VariableName": workspace_name},
                    metadata=metadata,
                )
            else:
                raise DeterministicCompileError(
                    f"No numeric value or input signal provided for symbol input {symbol_name!r}."
                )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            return source

        if op != "integrator" and numeric_value is not None:
            block_id = self.add_block(
                f"const_{node_id}",
                "Constant",
                system=owner,
                name=f"const_{_sanitize_for_id(node_id)}",
                params={"Value": _numeric_string(numeric_value)},
                metadata={
                    "layout_role": "shared" if owner == ROOT_SYSTEM else "compute",
                    "trace_expression": self.node_expressions[node_id],
                    "layer_hint": self.node_layers.get(node_id, 0),
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            return source

        if op == "integrator":
            state_name = str(node.get("state", ""))
            params: dict[str, object] = {}
            if state_name in self.initial_conditions:
                params["InitialCondition"] = _numeric_string(self.initial_conditions[state_name])
            block_id = self.add_block(
                f"int_{_sanitize_for_id(state_name)}",
                "Integrator",
                system=owner,
                name=f"int_{state_name}",
                params=params,
                metadata={
                    "layout_role": "integrator",
                    "state": state_name,
                    "state_order": state_order(state_name),
                    "trace_expression": state_name,
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            rhs_node_id = node["inputs"][0]
            rhs_source = self.resolve_for_system(rhs_node_id, owner)
            self.add_connection(owner, rhs_source, block_id, 1, label=self.node_expressions[rhs_node_id])
            return source

        layer_hint = self.node_layers.get(node_id, 0)
        layout_role = "shared" if owner == ROOT_SYSTEM else "compute"

        if op in {"add", "sum"}:
            block_id = self.add_block(
                f"sum_{node_id}",
                "Sum",
                system=owner,
                name=f"sum_{_sanitize_for_id(node_id)}",
                params={"Inputs": "+" * len(node["inputs"])},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            for index, child_id in enumerate(node["inputs"], start=1):
                self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, index, label=self.node_expressions[child_id])
            return source

        if op in {"mul", "gain"}:
            child_values = [self.numeric_value(child_id) for child_id in node["inputs"]]
            dynamic_children = [child_id for child_id, value in zip(node["inputs"], child_values) if value is None]
            if len(node["inputs"]) == 2 and len(dynamic_children) == 1:
                gain_value = next(value for value in child_values if value is not None)
                block_id = self.add_block(
                    f"gain_{node_id}",
                    "Gain",
                    system=owner,
                    name=f"gain_{_sanitize_for_id(node_id)}",
                    params={"Gain": _numeric_string(gain_value)},
                    metadata={
                        "layout_role": layout_role,
                        "layer_hint": layer_hint,
                        "trace_expression": self.node_expressions[node_id],
                    },
                )
                source = (block_id, "1")
                self.local_source_cache[node_id] = source
                child_id = dynamic_children[0]
                self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
                return source

            block_id = self.add_block(
                f"prod_{node_id}",
                "Product",
                system=owner,
                name=f"prod_{_sanitize_for_id(node_id)}",
                params={"Inputs": "*" * len(node["inputs"])},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            for index, child_id in enumerate(node["inputs"], start=1):
                self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, index, label=self.node_expressions[child_id])
            return source

        if op == "div":
            numerator_id, denominator_id = node["inputs"]
            denominator_value = self.numeric_value(denominator_id)
            if denominator_value is not None and self.numeric_value(numerator_id) is None:
                block_id = self.add_block(
                    f"gain_{node_id}",
                    "Gain",
                    system=owner,
                    name=f"gain_{_sanitize_for_id(node_id)}",
                    params={"Gain": _numeric_string(1.0 / denominator_value)},
                    metadata={
                        "layout_role": layout_role,
                        "layer_hint": layer_hint,
                        "trace_expression": self.node_expressions[node_id],
                    },
                )
                source = (block_id, "1")
                self.local_source_cache[node_id] = source
                self.add_connection(owner, self.resolve_for_system(numerator_id, owner), block_id, 1, label=self.node_expressions[numerator_id])
                return source

            block_id = self.add_block(
                f"div_{node_id}",
                "Divide",
                system=owner,
                name=f"div_{_sanitize_for_id(node_id)}",
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            self.add_connection(owner, self.resolve_for_system(numerator_id, owner), block_id, 1, label=self.node_expressions[numerator_id])
            self.add_connection(owner, self.resolve_for_system(denominator_id, owner), block_id, 2, label=self.node_expressions[denominator_id])
            return source

        if op == "negate":
            block_id = self.add_block(
                f"neg_{node_id}",
                "Gain",
                system=owner,
                name=f"neg_{_sanitize_for_id(node_id)}",
                params={"Gain": "-1"},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            child_id = node["inputs"][0]
            self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
            return source

        if op in DIRECT_SIMULINK_TRIG_FUNCTIONS:
            block_id = self.add_block(
                f"{op}_{node_id}",
                "TrigonometricFunction",
                system=owner,
                name=f"{op}_{_sanitize_for_id(node_id)}",
                params={"Operator": op},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            child_id = node["inputs"][0]
            self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
            return source

        if op in RECIPROCAL_FUNCTION_BASES:
            base_op = RECIPROCAL_FUNCTION_BASES[op]
            trig_id = self.add_block(
                f"{base_op}_{node_id}",
                "TrigonometricFunction",
                system=owner,
                name=f"{base_op}_{_sanitize_for_id(node_id)}",
                params={"Operator": base_op},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": f"{base_op}(...)",
                },
            )
            child_id = node["inputs"][0]
            self.add_connection(owner, self.resolve_for_system(child_id, owner), trig_id, 1, label=self.node_expressions[child_id])
            one_id = self.add_block(
                f"const_one_{node_id}",
                "Constant",
                system=owner,
                name=f"const_one_{_sanitize_for_id(node_id)}",
                params={"Value": "1"},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": max(0, layer_hint - 1),
                    "trace_expression": "1",
                },
            )
            div_id = self.add_block(
                f"{op}_{node_id}",
                "Divide",
                system=owner,
                name=f"{op}_{_sanitize_for_id(node_id)}",
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (div_id, "1")
            self.local_source_cache[node_id] = source
            self.add_connection(owner, (one_id, "1"), div_id, 1, label="1")
            self.add_connection(owner, (trig_id, "1"), div_id, 2, label=f"{base_op}({self.node_expressions[child_id]})")
            return source

        if op in DIRECT_SIMULINK_MATH_FUNCTIONS:
            block_id = self.add_block(
                f"{op}_{node_id}",
                "MathFunction",
                system=owner,
                name=f"{op}_{_sanitize_for_id(node_id)}",
                params={"Operator": op},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (block_id, "1")
            self.local_source_cache[node_id] = source
            child_id = node["inputs"][0]
            self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
            return source

        if op == "pow":
            base_id, exponent_id = node["inputs"]
            exponent_value = self.numeric_value(exponent_id)
            if exponent_value is None:
                raise DeterministicCompileError(f"Power node {node_id!r} requires a numeric exponent.")
            rounded = int(round(exponent_value))
            if math.isclose(exponent_value, 0.0, rel_tol=0.0, abs_tol=1e-12):
                block_id = self.add_block(
                    f"const_{node_id}",
                    "Constant",
                    system=owner,
                    name=f"const_{_sanitize_for_id(node_id)}",
                    params={"Value": "1"},
                    metadata={
                        "layout_role": layout_role,
                        "layer_hint": layer_hint,
                        "trace_expression": "1",
                    },
                )
                source = (block_id, "1")
                self.local_source_cache[node_id] = source
                return source
            if math.isclose(exponent_value, 1.0, rel_tol=0.0, abs_tol=1e-12):
                source = self.resolve_for_system(base_id, owner)
                self.local_source_cache[node_id] = source
                return source
            if math.isclose(exponent_value, rounded, rel_tol=0.0, abs_tol=1e-12):
                magnitude = abs(rounded)
                if magnitude == 1:
                    power_source = self.resolve_for_system(base_id, owner)
                else:
                    block_id = self.add_block(
                        f"prod_{node_id}",
                        "Product",
                        system=owner,
                        name=f"prod_{_sanitize_for_id(node_id)}",
                        params={"Inputs": "*" * magnitude},
                        metadata={
                            "layout_role": layout_role,
                            "layer_hint": layer_hint,
                            "trace_expression": self.node_expressions[node_id],
                        },
                    )
                    power_source = (block_id, "1")
                    self.local_source_cache[node_id] = power_source
                    base_source = self.resolve_for_system(base_id, owner)
                    for index in range(1, magnitude + 1):
                        self.add_connection(owner, base_source, block_id, index, label=self.node_expressions[base_id])
                if rounded > 0:
                    self.local_source_cache[node_id] = power_source
                    return power_source
                one_id = self.add_block(
                    f"const_one_{node_id}",
                    "Constant",
                    system=owner,
                    name=f"const_one_{_sanitize_for_id(node_id)}",
                    params={"Value": "1"},
                    metadata={
                        "layout_role": layout_role,
                        "layer_hint": max(0, layer_hint - 1),
                        "trace_expression": "1",
                    },
                )
                div_id = self.add_block(
                    f"pow_recip_{node_id}",
                    "Divide",
                    system=owner,
                    name=f"pow_recip_{_sanitize_for_id(node_id)}",
                    metadata={
                        "layout_role": layout_role,
                        "layer_hint": layer_hint,
                        "trace_expression": self.node_expressions[node_id],
                    },
                )
                source = (div_id, "1")
                self.local_source_cache[node_id] = source
                self.add_connection(owner, (one_id, "1"), div_id, 1, label="1")
                self.add_connection(owner, power_source, div_id, 2, label=self.node_expressions[node_id])
                return source

            log_id = self.add_block(
                f"log_{node_id}",
                "MathFunction",
                system=owner,
                name=f"log_{_sanitize_for_id(node_id)}",
                params={"Operator": "log"},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": max(0, layer_hint - 2),
                    "trace_expression": f"log({self.node_expressions[base_id]})",
                },
            )
            gain_id = self.add_block(
                f"pow_gain_{node_id}",
                "Gain",
                system=owner,
                name=f"pow_gain_{_sanitize_for_id(node_id)}",
                params={"Gain": _numeric_string(exponent_value)},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": max(0, layer_hint - 1),
                    "trace_expression": f"{_numeric_string(exponent_value)} * log({self.node_expressions[base_id]})",
                },
            )
            exp_id = self.add_block(
                f"exp_{node_id}",
                "MathFunction",
                system=owner,
                name=f"exp_{_sanitize_for_id(node_id)}",
                params={"Operator": "exp"},
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = (exp_id, "1")
            self.local_source_cache[node_id] = source
            base_source = self.resolve_for_system(base_id, owner)
            self.add_connection(owner, base_source, log_id, 1, label=self.node_expressions[base_id])
            self.add_connection(owner, (log_id, "1"), gain_id, 1, label=f"log({self.node_expressions[base_id]})")
            self.add_connection(owner, (gain_id, "1"), exp_id, 1, label=f"{_numeric_string(exponent_value)} * log({self.node_expressions[base_id]})")
            return source

        raise DeterministicCompileError(f"Unsupported graph op {op!r} in Simulink lowering.")

    def lower(self, state_names: list[str] | None = None, model_params: dict[str, object] | None = None) -> BackendSimulinkModelDict:
        """Lower the graph to a hierarchical, labeled, and laid-out Simulink model dictionary."""
        output_states = state_names or list(self.state_chain_map)
        outputs: list[dict[str, str]] = []

        for index, state in enumerate(output_states, start=1):
            if state not in self.state_chain_map:
                raise DeterministicCompileError(f"Requested Simulink output {state!r} not found in graph state chains.")
            signal_id = self.state_chain_map[state]["signal"]
            signal_source = self.resolve_for_system(signal_id, ROOT_SYSTEM)
            out_block_id = self.add_block(
                f"out_{_sanitize_for_id(state)}",
                "Outport",
                system=ROOT_SYSTEM,
                name=f"out_{state}",
                params={"Port": index},
                metadata={
                    "layout_role": "output",
                    "trace_expression": state,
                },
            )
            self.add_connection(ROOT_SYSTEM, signal_source, out_block_id, 1, label=self.node_expressions[signal_id])
            outputs.append({"name": state, "block": out_block_id, "port": "1"})

        model = validate_simulink_model_dict(
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
                    "node_expressions": self.node_expressions,
                    "state_groups": self.state_groups,
                },
            }
        )
        annotate_integrator_orders(model)
        return validate_simulink_model_dict(apply_deterministic_layout(model))


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
    """Lower a validated graph dictionary into a hierarchical Simulink-ready model dictionary."""
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
