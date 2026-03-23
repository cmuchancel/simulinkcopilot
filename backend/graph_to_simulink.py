"""Hierarchical graph-to-Simulink lowering with deterministic layout and traceability."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.block_library import BLOCK_LIBRARY
from backend.graph_numeric import GraphNumericEvaluator, safe_reciprocal as _safe_reciprocal
from backend.graph_partition import build_graph_subsystem_plan
from backend.layout import annotate_integrator_orders, apply_deterministic_layout
from backend.simulink_dict import ROOT_SYSTEM, SUBSYSTEM_BLOCK, BackendSimulinkModelDict, validate_simulink_model_dict
from backend.traceability import build_node_expressions, state_base_name, state_order
from ir.graph_validate import validate_graph_dict
from latex_frontend.symbols import (
    DeterministicCompileError,
    DIRECT_SIMULINK_BINARY_TRIG_FUNCTIONS,
    DIRECT_SIMULINK_MATH_FUNCTIONS,
    DIRECT_SIMULINK_MINMAX_FUNCTIONS,
    DIRECT_SIMULINK_SATURATION_FUNCTIONS,
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


def _group_key_for_state(state: str) -> str:
    return state_base_name(state)


@dataclass
class GraphToSimulinkLowerer:
    graph: dict[str, object]
    model_name: str
    symbol_values: dict[str, float] = field(default_factory=dict)
    input_signals: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    algebraic_initial_conditions: dict[str, float] = field(default_factory=dict)
    input_mode: str = "constant"
    blocks: dict[str, dict[str, object]] = field(default_factory=dict)
    connections: list[dict[str, object]] = field(default_factory=list)
    local_source_cache: dict[str, tuple[str, str]] = field(default_factory=dict)
    import_cache: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    export_cache: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    workspace_variables: dict[str, object] = field(default_factory=dict)
    inport_counters: dict[str, int] = field(default_factory=dict)
    outport_counters: dict[str, int] = field(default_factory=dict)
    numeric_evaluator: GraphNumericEvaluator = field(init=False)

    def __post_init__(self) -> None:
        self.graph = validate_graph_dict(self.graph)
        self.node_map = {node["id"]: node for node in self.graph["nodes"]}  # type: ignore[index]
        self.state_chain_map = {
            entry["state"]: entry
            for entry in self.graph.get("state_chains", [])  # type: ignore[index]
        }
        self.algebraic_chain_map = {
            entry["variable"]: entry
            for entry in self.graph.get("algebraic_chains", [])  # type: ignore[index]
        }
        self.node_expressions = build_node_expressions(self.graph)
        plan = build_graph_subsystem_plan(
            self.node_map,
            self.state_chain_map,
            root_system=ROOT_SYSTEM,
            group_key_for_state=_group_key_for_state,
            subsystem_id_for_group=self._subsystem_block_id,
        )
        self.state_groups = list(plan.state_groups)
        self.node_groups = plan.node_groups
        self.node_owners = plan.node_owners
        self.node_layers = plan.node_layers
        self.numeric_evaluator = GraphNumericEvaluator(
            node_map=self.node_map,
            symbol_values=self.symbol_values,
        )
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

    def _subsystem_block_id(self, group: str) -> str:
        return f"subsystem_{_sanitize_for_id(group)}"

    def numeric_value(self, node_id: str) -> float | None:
        """Return a numeric value if the node subtree is compile-time evaluable."""
        return self.numeric_evaluator.value(node_id)

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

    def _remember_source(self, node_id: str, source: tuple[str, str]) -> tuple[str, str]:
        self.local_source_cache[node_id] = source
        return source

    def _materialize_constant_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
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
        return self._remember_source(node_id, (block_id, "1"))

    def _materialize_symbol_input_node(self, node_id: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        symbol_name = str(node["name"])
        symbol_role = str(node.get("symbol_role", ""))
        metadata = {
            "layout_role": "source",
            "trace_expression": self.node_expressions[node_id],
            "layer_hint": 0,
        }
        if symbol_role == "independent_variable":
            block_id = self.add_block(
                f"time_{_sanitize_for_id(symbol_name)}",
                "Clock",
                system=ROOT_SYSTEM,
                name=symbol_name,
                metadata=metadata,
            )
        elif symbol_role == "algebraic_variable":
            params: dict[str, object] = {}
            if symbol_name in self.algebraic_initial_conditions:
                params["InitialGuess"] = _numeric_string(self.algebraic_initial_conditions[symbol_name])
            block_id = self.add_block(
                f"algebraic_{_sanitize_for_id(symbol_name)}",
                "AlgebraicConstraint",
                system=ROOT_SYSTEM,
                name=symbol_name,
                params=params,
                metadata=metadata,
            )
        elif symbol_name in self.symbol_values:
            block_id = self.add_block(
                f"symbol_{_sanitize_for_id(symbol_name)}",
                "Constant",
                system=ROOT_SYSTEM,
                name=symbol_name,
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
                name=symbol_name,
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
                name=symbol_name,
                params={"VariableName": workspace_name},
                metadata=metadata,
            )
        else:
            raise DeterministicCompileError(
                f"No numeric value or input signal provided for symbol input {symbol_name!r}."
            )
        return self._remember_source(node_id, (block_id, "1"))

    def _materialize_folded_constant_node(
        self,
        node_id: str,
        *,
        owner: str,
        numeric_value: float,
    ) -> tuple[str, str]:
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
        return self._remember_source(node_id, (block_id, "1"))

    def _materialize_integrator_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
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
        source = self._remember_source(node_id, (block_id, "1"))
        rhs_node_id = node["inputs"][0]
        rhs_source = self.resolve_for_system(rhs_node_id, owner)
        self.add_connection(owner, rhs_source, block_id, 1, label=self.node_expressions[rhs_node_id])
        return source

    def _operator_metadata(self, node_id: str, *, owner: str) -> tuple[int, str]:
        layer_hint = self.node_layers.get(node_id, 0)
        layout_role = "shared" if owner == ROOT_SYSTEM else "compute"
        return layer_hint, layout_role

    def _materialize_sum_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
        source = self._remember_source(node_id, (block_id, "1"))
        for index, child_id in enumerate(node["inputs"], start=1):
            self.add_connection(
                owner,
                self.resolve_for_system(child_id, owner),
                block_id,
                index,
                label=self.node_expressions[child_id],
            )
        return source

    def _materialize_product_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
            source = self._remember_source(node_id, (block_id, "1"))
            child_id = dynamic_children[0]
            self.add_connection(
                owner,
                self.resolve_for_system(child_id, owner),
                block_id,
                1,
                label=self.node_expressions[child_id],
            )
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
        source = self._remember_source(node_id, (block_id, "1"))
        for index, child_id in enumerate(node["inputs"], start=1):
            self.add_connection(
                owner,
                self.resolve_for_system(child_id, owner),
                block_id,
                index,
                label=self.node_expressions[child_id],
            )
        return source

    def _materialize_division_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
            source = self._remember_source(node_id, (block_id, "1"))
            self.add_connection(
                owner,
                self.resolve_for_system(numerator_id, owner),
                block_id,
                1,
                label=self.node_expressions[numerator_id],
            )
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
        source = self._remember_source(node_id, (block_id, "1"))
        self.add_connection(owner, self.resolve_for_system(numerator_id, owner), block_id, 1, label=self.node_expressions[numerator_id])
        self.add_connection(owner, self.resolve_for_system(denominator_id, owner), block_id, 2, label=self.node_expressions[denominator_id])
        return source

    def _materialize_negate_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
        source = self._remember_source(node_id, (block_id, "1"))
        child_id = node["inputs"][0]
        self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
        return source

    def _materialize_trig_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        op = str(node["op"])
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
        source = self._remember_source(node_id, (block_id, "1"))
        child_id = node["inputs"][0]
        self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
        return source

    def _materialize_binary_trig_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        op = str(node["op"])
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
        source = self._remember_source(node_id, (block_id, "1"))
        for index, child_id in enumerate(node["inputs"], start=1):
            self.add_connection(
                owner,
                self.resolve_for_system(child_id, owner),
                block_id,
                index,
                label=self.node_expressions[child_id],
            )
        return source

    def _materialize_reciprocal_trig_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        op = str(node["op"])
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
        source = self._remember_source(node_id, (div_id, "1"))
        self.add_connection(owner, (one_id, "1"), div_id, 1, label="1")
        self.add_connection(owner, (trig_id, "1"), div_id, 2, label=f"{base_op}({self.node_expressions[child_id]})")
        return source

    def _materialize_abs_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
        block_id = self.add_block(
            f"abs_{node_id}",
            "Abs",
            system=owner,
            name=f"abs_{_sanitize_for_id(node_id)}",
            metadata={
                "layout_role": layout_role,
                "layer_hint": layer_hint,
                "trace_expression": self.node_expressions[node_id],
            },
        )
        source = self._remember_source(node_id, (block_id, "1"))
        child_id = node["inputs"][0]
        self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
        return source

    def _materialize_math_function_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        op = str(node["op"])
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
        source = self._remember_source(node_id, (block_id, "1"))
        child_id = node["inputs"][0]
        self.add_connection(owner, self.resolve_for_system(child_id, owner), block_id, 1, label=self.node_expressions[child_id])
        return source

    def _materialize_minmax_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        op = str(node["op"])
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
        block_id = self.add_block(
            f"{op}_{node_id}",
            "MinMax",
            system=owner,
            name=f"{op}_{_sanitize_for_id(node_id)}",
            params={"Function": op, "Inputs": str(len(node["inputs"]))},
            metadata={
                "layout_role": layout_role,
                "layer_hint": layer_hint,
                "trace_expression": self.node_expressions[node_id],
            },
        )
        source = self._remember_source(node_id, (block_id, "1"))
        for index, child_id in enumerate(node["inputs"], start=1):
            self.add_connection(
                owner,
                self.resolve_for_system(child_id, owner),
                block_id,
                index,
                label=self.node_expressions[child_id],
            )
        return source

    def _materialize_saturation_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
        input_id, lower_id, upper_id = node["inputs"]
        lower_value = self.numeric_value(lower_id)
        upper_value = self.numeric_value(upper_id)

        if lower_value is not None and upper_value is not None:
            block_id = self.add_block(
                f"sat_{node_id}",
                "Saturation",
                system=owner,
                name=f"sat_{_sanitize_for_id(node_id)}",
                params={
                    "LowerLimit": _numeric_string(lower_value),
                    "UpperLimit": _numeric_string(upper_value),
                },
                metadata={
                    "layout_role": layout_role,
                    "layer_hint": layer_hint,
                    "trace_expression": self.node_expressions[node_id],
                },
            )
            source = self._remember_source(node_id, (block_id, "1"))
            self.add_connection(
                owner,
                self.resolve_for_system(input_id, owner),
                block_id,
                1,
                label=self.node_expressions[input_id],
            )
            return source

        max_block_id = self.add_block(
            f"sat_max_{node_id}",
            "MinMax",
            system=owner,
            name=f"sat_max_{_sanitize_for_id(node_id)}",
            params={"Function": "max", "Inputs": "2"},
            metadata={
                "layout_role": layout_role,
                "layer_hint": max(0, layer_hint - 1),
                "trace_expression": f"max({self.node_expressions[input_id]}, {self.node_expressions[lower_id]})",
            },
        )
        min_block_id = self.add_block(
            f"sat_min_{node_id}",
            "MinMax",
            system=owner,
            name=f"sat_min_{_sanitize_for_id(node_id)}",
            params={"Function": "min", "Inputs": "2"},
            metadata={
                "layout_role": layout_role,
                "layer_hint": layer_hint,
                "trace_expression": self.node_expressions[node_id],
            },
        )
        source = self._remember_source(node_id, (min_block_id, "1"))
        self.add_connection(
            owner,
            self.resolve_for_system(input_id, owner),
            max_block_id,
            1,
            label=self.node_expressions[input_id],
        )
        self.add_connection(
            owner,
            self.resolve_for_system(lower_id, owner),
            max_block_id,
            2,
            label=self.node_expressions[lower_id],
        )
        self.add_connection(
            owner,
            (max_block_id, "1"),
            min_block_id,
            1,
            label=f"max({self.node_expressions[input_id]}, {self.node_expressions[lower_id]})",
        )
        self.add_connection(
            owner,
            self.resolve_for_system(upper_id, owner),
            min_block_id,
            2,
            label=self.node_expressions[upper_id],
        )
        return source

    def _materialize_power_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
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
            return self._remember_source(node_id, (block_id, "1"))
        if math.isclose(exponent_value, 1.0, rel_tol=0.0, abs_tol=1e-12):
            source = self.resolve_for_system(base_id, owner)
            return self._remember_source(node_id, source)
        if math.isclose(exponent_value, rounded, rel_tol=0.0, abs_tol=1e-12):
            return self._materialize_integer_power_node(
                node_id,
                owner=owner,
                layer_hint=layer_hint,
                layout_role=layout_role,
                base_id=base_id,
                exponent_value=rounded,
            )
        return self._materialize_fractional_power_node(
            node_id,
            owner=owner,
            layer_hint=layer_hint,
            layout_role=layout_role,
            base_id=base_id,
            exponent_value=exponent_value,
        )

    def _materialize_integer_power_node(
        self,
        node_id: str,
        *,
        owner: str,
        layer_hint: int,
        layout_role: str,
        base_id: str,
        exponent_value: int,
    ) -> tuple[str, str]:
        magnitude = abs(exponent_value)
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
            power_source = self._remember_source(node_id, (block_id, "1"))
            base_source = self.resolve_for_system(base_id, owner)
            for index in range(1, magnitude + 1):
                self.add_connection(owner, base_source, block_id, index, label=self.node_expressions[base_id])
        if exponent_value > 0:
            return self._remember_source(node_id, power_source)

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
        source = self._remember_source(node_id, (div_id, "1"))
        self.add_connection(owner, (one_id, "1"), div_id, 1, label="1")
        self.add_connection(owner, power_source, div_id, 2, label=self.node_expressions[node_id])
        return source

    def _materialize_fractional_power_node(
        self,
        node_id: str,
        *,
        owner: str,
        layer_hint: int,
        layout_role: str,
        base_id: str,
        exponent_value: float,
    ) -> tuple[str, str]:
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
        source = self._remember_source(node_id, (exp_id, "1"))
        base_source = self.resolve_for_system(base_id, owner)
        self.add_connection(owner, base_source, log_id, 1, label=self.node_expressions[base_id])
        self.add_connection(owner, (log_id, "1"), gain_id, 1, label=f"log({self.node_expressions[base_id]})")
        self.add_connection(owner, (gain_id, "1"), exp_id, 1, label=f"{_numeric_string(exponent_value)} * log({self.node_expressions[base_id]})")
        return source

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
            return self._materialize_constant_node(node_id, owner=owner)

        if op == "symbol_input":
            return self._materialize_symbol_input_node(node_id)

        if op != "integrator" and numeric_value is not None:
            return self._materialize_folded_constant_node(node_id, owner=owner, numeric_value=numeric_value)

        if op == "integrator":
            return self._materialize_integrator_node(node_id, owner=owner)

        if op in {"add", "sum"}:
            return self._materialize_sum_node(node_id, owner=owner)

        if op in {"mul", "gain"}:
            return self._materialize_product_node(node_id, owner=owner)

        if op == "div":
            return self._materialize_division_node(node_id, owner=owner)

        if op == "negate":
            return self._materialize_negate_node(node_id, owner=owner)

        if op in DIRECT_SIMULINK_TRIG_FUNCTIONS:
            return self._materialize_trig_node(node_id, owner=owner)

        if op in DIRECT_SIMULINK_BINARY_TRIG_FUNCTIONS:
            return self._materialize_binary_trig_node(node_id, owner=owner)

        if op in RECIPROCAL_FUNCTION_BASES:
            return self._materialize_reciprocal_trig_node(node_id, owner=owner)

        if op == "abs":
            return self._materialize_abs_node(node_id, owner=owner)

        if op in DIRECT_SIMULINK_MATH_FUNCTIONS:
            return self._materialize_math_function_node(node_id, owner=owner)

        if op in DIRECT_SIMULINK_MINMAX_FUNCTIONS:
            return self._materialize_minmax_node(node_id, owner=owner)

        if op in DIRECT_SIMULINK_SATURATION_FUNCTIONS:
            return self._materialize_saturation_node(node_id, owner=owner)

        if op == "pow":
            return self._materialize_power_node(node_id, owner=owner)

        raise DeterministicCompileError(f"Unsupported graph op {op!r} in Simulink lowering.")

    def _wire_algebraic_constraints(self) -> None:
        for variable, chain in self.algebraic_chain_map.items():
            source = self.resolve_for_system(chain["signal"], ROOT_SYSTEM)
            residual_source = self.resolve_for_system(chain["residual"], ROOT_SYSTEM)
            self.add_connection(
                ROOT_SYSTEM,
                residual_source,
                source[0],
                1,
                label=self.node_expressions[chain["residual"]],
            )

    def lower(self, state_names: list[str] | None = None, model_params: dict[str, object] | None = None) -> BackendSimulinkModelDict:
        """Lower the graph to a hierarchical, labeled, and laid-out Simulink model dictionary."""
        requested_outputs = state_names or [*self.state_chain_map, *self.algebraic_chain_map]
        self._wire_algebraic_constraints()
        outputs: list[dict[str, str]] = []

        for index, state in enumerate(requested_outputs, start=1):
            if state in self.state_chain_map:
                signal_id = self.state_chain_map[state]["signal"]
            elif state in self.algebraic_chain_map:
                signal_id = self.algebraic_chain_map[state]["signal"]
            else:
                raise DeterministicCompileError(
                    f"Requested Simulink output {state!r} not found in graph state or algebraic chains."
                )
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
                    "state_names": [name for name in requested_outputs if name in self.state_chain_map],
                    "algebraic_variables": [name for name in requested_outputs if name in self.algebraic_chain_map],
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
    algebraic_initial_conditions: dict[str, float] | None = None,
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
        algebraic_initial_conditions=dict(algebraic_initial_conditions or {}),
        input_mode=input_mode,
    )
    return lowerer.lower(state_names=state_names, model_params=model_params)
