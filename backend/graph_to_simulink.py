"""Hierarchical graph-to-Simulink lowering with deterministic layout and traceability."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.block_library import BLOCK_LIBRARY
from backend.graph_numeric import GraphNumericEvaluator, safe_reciprocal
from backend.graph_partition import build_graph_subsystem_plan
from backend.layout import annotate_integrator_orders
from backend.layout_visual_corrector import VisualRepairConfig
from backend.layout_workflow import LayoutMode, apply_layout_workflow
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
from simulate.input_specs import normalize_input_specs
from simulink.utils import sanitize_block_name

_safe_reciprocal = safe_reciprocal


def _numeric_string(value: float | int) -> str:
    if float(value).is_integer():
        return str(int(round(float(value))))
    return repr(float(value))


def _sanitize_for_id(name: str) -> str:
    return sanitize_block_name(name)


def _group_key_for_state(state: str) -> str:
    return state_base_name(state)


def _matrix_signal_literal(time_values: list[float], sample_values: list[float]) -> str:
    rows = [
        f"{repr(float(time_value))} {repr(float(sample_value))}"
        for time_value, sample_value in zip(time_values, sample_values)
    ]
    return "[" + "; ".join(rows) + "]"


@dataclass
class GraphToSimulinkLowerer:
    graph: dict[str, object]
    model_name: str
    symbol_values: dict[str, float] = field(default_factory=dict)
    input_specs: dict[str, dict[str, object]] = field(default_factory=dict)
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
    symbol_dependency_cache: dict[str, bool] = field(default_factory=dict)
    native_input_counter: int = 0
    numeric_evaluator: GraphNumericEvaluator = field(init=False)
    use_state_subsystems: bool = field(init=False, default=True)

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
        self.use_state_subsystems = len(plan.state_groups) > 1
        if self.use_state_subsystems:
            self.node_owners = plan.node_owners
        else:
            self.node_owners = {node_id: ROOT_SYSTEM for node_id in self.node_map}
        self.node_layers = plan.node_layers
        self.numeric_evaluator = GraphNumericEvaluator(
            node_map=self.node_map,
            symbol_values=self.symbol_values,
        )
        if self.use_state_subsystems:
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

    def _is_symbol_input_node(self, node_id: str) -> bool:
        return str(self.node_map[node_id]["op"]) == "symbol_input"

    def _is_literal_constant_node(self, node_id: str, expected_value: float | None = None) -> bool:
        node = self.node_map[node_id]
        if str(node["op"]) != "constant":
            return False
        if expected_value is None:
            return True
        return math.isclose(float(node["value"]), float(expected_value), rel_tol=0.0, abs_tol=1e-12)

    def _depends_on_symbol_input(self, node_id: str) -> bool:
        cached = self.symbol_dependency_cache.get(node_id)
        if cached is not None:
            return cached
        node = self.node_map[node_id]
        if str(node["op"]) == "symbol_input":
            self.symbol_dependency_cache[node_id] = True
            return True
        depends = any(self._depends_on_symbol_input(str(child_id)) for child_id in node.get("inputs", []))
        self.symbol_dependency_cache[node_id] = depends
        return depends

    def _native_input_spec(self, symbol_name: str) -> dict[str, object] | None:
        spec = self.input_specs.get(symbol_name)
        if spec is None:
            return None
        if self._is_supported_native_input_spec(spec):
            return spec
        return None

    def _is_supported_native_input_spec(self, spec: dict[str, object]) -> bool:
        kind = str(spec.get("kind", ""))
        if kind in {
            "constant",
            "time",
            "step",
            "impulse",
            "pulse",
            "sine",
            "square",
            "sawtooth",
            "triangle",
            "ramp",
            "random_number",
            "white_noise",
            "expression",
        }:
            return True
        if kind in {"sum", "product"}:
            terms = spec.get("terms")
            return isinstance(terms, list) and bool(terms) and all(
                isinstance(term, dict) and self._is_supported_native_input_spec(term) for term in terms
            )
        if kind in {
            "power",
            "exp",
            "delay",
            "trig_function",
            "reciprocal_trig_function",
            "math_function",
            "saturation",
            "dead_zone",
            "abs",
            "sign",
            "relay",
        }:
            inner = spec.get("input")
            return isinstance(inner, dict) and self._is_supported_native_input_spec(inner)
        if kind == "binary_trig_function":
            lhs = spec.get("lhs")
            rhs = spec.get("rhs")
            return (
                isinstance(lhs, dict)
                and self._is_supported_native_input_spec(lhs)
                and isinstance(rhs, dict)
                and self._is_supported_native_input_spec(rhs)
            )
        if kind == "minmax":
            terms = spec.get("terms")
            return isinstance(terms, list) and bool(terms) and all(
                isinstance(term, dict) and self._is_supported_native_input_spec(term) for term in terms
            )
        if kind == "piecewise":
            branches = spec.get("branches")
            otherwise = spec.get("otherwise")
            return (
                isinstance(branches, list)
                and bool(branches)
                and all(
                    isinstance(branch, dict)
                    and isinstance(branch.get("value"), dict)
                    and self._is_supported_native_input_spec(branch["value"])
                    and self._is_supported_native_condition_spec(branch.get("condition"))
                    for branch in branches
                )
                and isinstance(otherwise, dict)
                and self._is_supported_native_input_spec(otherwise)
            )
        return False

    def _is_supported_native_condition_spec(self, condition: object) -> bool:
        if not isinstance(condition, dict):
            return False
        kind = str(condition.get("kind", ""))
        if kind == "boolean":
            return isinstance(condition.get("value"), bool)
        if kind == "compare":
            return (
                str(condition.get("op", "")) in {"<", "<=", ">", ">=", "==", "!="}
                and isinstance(condition.get("lhs"), dict)
                and self._is_supported_native_input_spec(condition["lhs"])
                and isinstance(condition.get("rhs"), dict)
                and self._is_supported_native_input_spec(condition["rhs"])
            )
        if kind in {"and", "or"}:
            terms = condition.get("terms")
            return isinstance(terms, list) and bool(terms) and all(
                self._is_supported_native_condition_spec(term) for term in terms
            )
        if kind == "not":
            return self._is_supported_native_condition_spec(condition.get("input"))
        return False

    def _next_native_input_id(self, symbol_name: str, prefix: str) -> str:
        self.native_input_counter += 1
        return f"input_{_sanitize_for_id(symbol_name)}_{prefix}_{self.native_input_counter:04d}"

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
        elif self._native_input_spec(symbol_name) is not None:
            block_id = self._materialize_native_input_source_block(
                symbol_name,
                self._native_input_spec(symbol_name),
                metadata=metadata,
            )
        elif symbol_name in self.input_signals:
            series = self.input_signals[symbol_name]
            times = list(series["time"])
            values = list(series["values"])
            if len(times) != len(values):
                raise DeterministicCompileError(
                    f"Input signal {symbol_name!r} has mismatched time/value lengths."
                )
            block_id = self.add_block(
                f"input_{_sanitize_for_id(symbol_name)}",
                "FromWorkspace",
                system=ROOT_SYSTEM,
                name=symbol_name,
                params={"VariableName": _matrix_signal_literal(times, values)},
                metadata=metadata,
            )
        else:
            raise DeterministicCompileError(
                f"No numeric value or input signal provided for symbol input {symbol_name!r}."
            )
        return self._remember_source(node_id, (block_id, "1"))

    def _materialize_native_input_source_block(
        self,
        symbol_name: str,
        spec: dict[str, object] | None,
        *,
        metadata: dict[str, object],
    ) -> str:
        if spec is None:
            raise DeterministicCompileError(f"Missing native input spec for {symbol_name!r}.")
        block_id, _ = self._build_native_input_source(symbol_name, spec, metadata=metadata, display_name=symbol_name)
        return block_id

    def _build_native_input_source(
        self,
        symbol_name: str,
        spec: dict[str, object],
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        kind = str(spec["kind"])
        if kind == "constant":
            return self._native_constant_source(
                symbol_name,
                float(spec.get("value", 0.0)),
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "time":
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "time"),
                "Clock",
                system=ROOT_SYSTEM,
                name=display_name,
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "step":
            bias = float(spec.get("bias", 0.0))
            amplitude = float(spec.get("amplitude", 1.0))
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "step"),
                "Step",
                system=ROOT_SYSTEM,
                name=display_name,
                params={
                    "Time": _numeric_string(float(spec.get("start_time", 0.0))),
                    "Before": _numeric_string(bias),
                    "After": _numeric_string(bias + amplitude),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "square":
            sine_ref = self._build_native_input_source(
                symbol_name,
                {
                    "kind": "sine",
                    "amplitude": 1.0,
                    "frequency": float(spec.get("frequency", 1.0)),
                    "phase": float(spec.get("phase", 0.0)),
                    "bias": 0.0,
                },
                metadata=metadata,
                display_name=f"{display_name}_src",
            )
            sign_ref = self._apply_native_unary_block(
                symbol_name,
                "Sign",
                sine_ref,
                metadata=metadata,
                display_name=f"{display_name}_sign",
                prefix="sign",
            )
            scaled_ref = self._apply_native_gain(
                symbol_name,
                sign_ref,
                gain=float(spec.get("amplitude", 1.0)),
                metadata=metadata,
                display_name=f"{display_name}_gain",
                prefix="square_gain",
            )
            return self._apply_native_bias(
                symbol_name,
                scaled_ref,
                bias=float(spec.get("bias", 0.0)),
                metadata=metadata,
                display_name=display_name,
            )
        if kind in {"sawtooth", "triangle"}:
            base_ref = self._build_repeating_sequence_source(
                symbol_name,
                spec,
                metadata=metadata,
                display_name=display_name,
            )
            return self._wrap_periodic_phase_delay(
                symbol_name,
                base_ref,
                frequency=float(spec.get("frequency", 1.0)),
                phase=float(spec.get("phase", 0.0)),
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "ramp":
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "ramp"),
                "Ramp",
                system=ROOT_SYSTEM,
                name=display_name,
                params={
                    "slope": _numeric_string(float(spec.get("slope", 1.0))),
                    "start": _numeric_string(float(spec.get("start_time", 0.0))),
                    "InitialOutput": _numeric_string(float(spec.get("initial_output", 0.0))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind in {"impulse", "pulse"}:
            amplitude = float(spec.get("amplitude", 1.0))
            width = float(spec.get("width", 1.0))
            if width <= 0.0:
                raise DeterministicCompileError(f"Native {kind} width for {symbol_name!r} must be positive.")
            bias = float(spec.get("bias", 0.0))
            if kind == "impulse":
                pulse_amplitude = amplitude / width
            else:
                pulse_amplitude = amplitude
            source_id = self.add_block(
                self._next_native_input_id(symbol_name, kind),
                "PulseGenerator",
                system=ROOT_SYSTEM,
                name=display_name if abs(bias) <= 1e-12 else f"{display_name}_{kind}",
                params={
                    "PulseType": "Time based",
                    "Amplitude": _numeric_string(pulse_amplitude),
                    "Period": _numeric_string(float(spec.get("period", max(width * 2.0, 1.0)))),
                    "PulseWidth": _numeric_string(100.0 * width / float(spec.get("period", max(width * 2.0, 1.0)))),
                    "PhaseDelay": _numeric_string(float(spec.get("start_time", 0.0))),
                },
                metadata=metadata,
            )
            source_ref = (source_id, "1")
            if abs(bias) <= 1e-12:
                return source_ref
            bias_ref = self._build_native_input_source(
                symbol_name,
                {"kind": "constant", "value": bias},
                metadata=metadata,
                display_name=f"{display_name}_bias",
            )
            return self._combine_native_sources(
                symbol_name,
                "sum",
                [bias_ref, source_ref],
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "sine":
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "sine"),
                "SineWave",
                system=ROOT_SYSTEM,
                name=display_name,
                params={
                    "Amplitude": _numeric_string(float(spec.get("amplitude", 1.0))),
                    "Frequency": _numeric_string(float(spec.get("frequency", 1.0))),
                    "Phase": _numeric_string(float(spec.get("phase", 0.0))),
                    "Bias": _numeric_string(float(spec.get("bias", 0.0))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind in {"sum", "product"}:
            terms = spec.get("terms")
            if not isinstance(terms, list) or not terms:
                raise DeterministicCompileError(
                    f"Native {kind} input spec for {symbol_name!r} requires a non-empty terms list."
                )
            term_refs = [
                self._build_native_input_source(
                    symbol_name,
                    term,
                    metadata=metadata,
                    display_name=f"{display_name}_term_{index + 1}",
                )
                for index, term in enumerate(terms)
            ]
            return self._combine_native_sources(
                symbol_name,
                kind,
                term_refs,
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "trig_function":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native trig_function input spec for {symbol_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_arg",
            )
            return self._apply_native_unary_block(
                symbol_name,
                "TrigonometricFunction",
                inner_ref,
                metadata=metadata,
                display_name=display_name,
                prefix=f"trig_{str(spec.get('operator', 'trig')).lower()}",
                params={"Operator": str(spec.get("operator", "")).lower()},
            )
        if kind == "binary_trig_function":
            lhs = spec.get("lhs")
            rhs = spec.get("rhs")
            if not isinstance(lhs, dict) or not isinstance(rhs, dict):
                raise DeterministicCompileError(
                    f"Native binary_trig_function input spec for {symbol_name!r} requires 'lhs' and 'rhs' sources."
                )
            lhs_ref = self._build_native_input_source(
                symbol_name,
                lhs,
                metadata=metadata,
                display_name=f"{display_name}_lhs",
            )
            rhs_ref = self._build_native_input_source(
                symbol_name,
                rhs,
                metadata=metadata,
                display_name=f"{display_name}_rhs",
            )
            operator = str(spec.get("operator", "")).lower()
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, f"trig_{operator}"),
                "TrigonometricFunction",
                system=ROOT_SYSTEM,
                name=display_name,
                params={"Operator": operator},
                metadata=metadata,
            )
            self.add_connection(ROOT_SYSTEM, lhs_ref, block_id, 1, label=display_name)
            self.add_connection(ROOT_SYSTEM, rhs_ref, block_id, 2, label=display_name)
            return (block_id, "1")
        if kind == "reciprocal_trig_function":
            inner = spec.get("input")
            operator = str(spec.get("operator", "")).lower()
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native reciprocal_trig_function input spec for {symbol_name!r} requires an 'input' source."
                )
            if operator not in RECIPROCAL_FUNCTION_BASES:
                raise DeterministicCompileError(
                    f"Unsupported reciprocal trig operator {operator!r} for {symbol_name!r}."
                )
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_arg",
            )
            trig_ref = self._apply_native_unary_block(
                symbol_name,
                "TrigonometricFunction",
                inner_ref,
                metadata=metadata,
                display_name=f"{display_name}_{RECIPROCAL_FUNCTION_BASES[operator]}",
                prefix=f"trig_{RECIPROCAL_FUNCTION_BASES[operator]}",
                params={"Operator": RECIPROCAL_FUNCTION_BASES[operator]},
            )
            one_ref = self._native_constant_source(
                symbol_name,
                1.0,
                metadata=metadata,
                display_name=f"{display_name}_one",
            )
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, f"recip_{operator}"),
                "Divide",
                system=ROOT_SYSTEM,
                name=display_name,
                metadata=metadata,
            )
            self.add_connection(ROOT_SYSTEM, one_ref, block_id, 1, label="1")
            self.add_connection(ROOT_SYSTEM, trig_ref, block_id, 2, label=display_name)
            return (block_id, "1")
        if kind == "math_function":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native math_function input spec for {symbol_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_arg",
            )
            return self._apply_native_unary_block(
                symbol_name,
                "MathFunction",
                inner_ref,
                metadata=metadata,
                display_name=display_name,
                prefix=f"math_{str(spec.get('operator', 'math')).lower()}",
                params={"Operator": str(spec.get("operator", "")).lower()},
            )
        if kind == "minmax":
            terms = spec.get("terms")
            if not isinstance(terms, list) or not terms:
                raise DeterministicCompileError(
                    f"Native minmax input spec for {symbol_name!r} requires a non-empty terms list."
                )
            term_refs = [
                self._build_native_input_source(
                    symbol_name,
                    term,
                    metadata=metadata,
                    display_name=f"{display_name}_{index + 1}",
                )
                for index, term in enumerate(terms)
            ]
            operator = str(spec.get("operator", "")).lower()
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, f"minmax_{operator}"),
                "MinMax",
                system=ROOT_SYSTEM,
                name=display_name,
                params={"Function": operator, "Inputs": str(len(term_refs))},
                metadata=metadata,
            )
            for index, term_ref in enumerate(term_refs, start=1):
                self.add_connection(ROOT_SYSTEM, term_ref, block_id, index, label=display_name)
            return (block_id, "1")
        if kind == "power":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(f"Native power input spec for {symbol_name!r} requires an 'input' source.")
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_src",
            )
            return self._build_power_native_source(
                symbol_name,
                inner_ref,
                exponent=float(spec.get("exponent", 1.0)),
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "exp":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native exponential input spec for {symbol_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_src",
            )
            return self._apply_native_unary_block(
                symbol_name,
                "MathFunction",
                inner_ref,
                metadata=metadata,
                display_name=display_name,
                prefix="exp",
                params={"Operator": "exp"},
            )
        if kind == "delay":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(f"Native delay input spec for {symbol_name!r} requires an 'input' source.")
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_src",
            )
            return self._apply_native_delay(
                symbol_name,
                inner_ref,
                delay_time=float(spec.get("delay_time", 0.0)),
                initial_output=float(spec.get("initial_output", 0.0)),
                metadata=metadata,
                display_name=display_name,
                prefix="delay",
            )
        if kind in {"saturation", "dead_zone", "abs", "sign", "relay"}:
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native {kind} input spec for {symbol_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                symbol_name,
                inner,
                metadata=metadata,
                display_name=f"{display_name}_src",
            )
            if kind == "saturation":
                block_type = "Saturation"
                prefix = "sat"
                params = {
                    "LowerLimit": _numeric_string(float(spec.get("lower_limit", -1.0))),
                    "UpperLimit": _numeric_string(float(spec.get("upper_limit", 1.0))),
                }
            elif kind == "dead_zone":
                block_type = "DeadZone"
                prefix = "deadzone"
                params = {
                    "LowerValue": _numeric_string(float(spec.get("lower_limit", -1.0))),
                    "UpperValue": _numeric_string(float(spec.get("upper_limit", 1.0))),
                }
            elif kind == "abs":
                block_type = "Abs"
                prefix = "abs"
                params = {}
            elif kind == "sign":
                block_type = "Sign"
                prefix = "sign"
                params = {}
            else:
                block_type = "Relay"
                prefix = "relay"
                params = {
                    "OnSwitchValue": _numeric_string(float(spec.get("on_switch_value", 0.0))),
                    "OffSwitchValue": _numeric_string(float(spec.get("off_switch_value", 0.0))),
                    "OnOutputValue": _numeric_string(float(spec.get("on_output_value", 1.0))),
                    "OffOutputValue": _numeric_string(float(spec.get("off_output_value", -1.0))),
                }
            return self._apply_native_unary_block(
                symbol_name,
                block_type,
                inner_ref,
                metadata=metadata,
                display_name=display_name,
                prefix=prefix,
                params=params,
            )
        if kind == "piecewise":
            return self._build_native_piecewise_source(
                symbol_name,
                spec,
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "random_number":
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "uniform_random"),
                "UniformRandomNumber",
                system=ROOT_SYSTEM,
                name=display_name,
                params={
                    "Minimum": _numeric_string(float(spec.get("minimum", 0.0))),
                    "Maximum": _numeric_string(float(spec.get("maximum", 1.0))),
                    "Seed": _numeric_string(float(spec.get("seed", 0.0))),
                    "SampleTime": _numeric_string(float(spec.get("sample_time", 0.01))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "white_noise":
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "random"),
                "RandomNumber",
                system=ROOT_SYSTEM,
                name=display_name,
                params={
                    "Mean": _numeric_string(float(spec.get("mean", 0.0))),
                    "Variance": _numeric_string(float(spec.get("variance", 1.0))),
                    "Seed": _numeric_string(float(spec.get("seed", 0.0))),
                    "SampleTime": _numeric_string(float(spec.get("sample_time", 0.01))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "expression":
            return self._build_expression_function_source(
                symbol_name,
                spec,
                metadata=metadata,
                display_name=display_name,
            )
        raise DeterministicCompileError(f"Unsupported native input spec kind {kind!r} for {symbol_name!r}.")

    def _build_expression_function_source(
        self,
        symbol_name: str,
        spec: dict[str, object],
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        expression_text = str(spec.get("expression", "")).strip()
        if not expression_text:
            raise DeterministicCompileError(f"Expression input spec for {symbol_name!r} requires a non-empty expression.")
        time_variable = str(spec.get("time_variable", "t")).strip() or "t"
        time_ref = self._build_native_input_source(
            symbol_name,
            {"kind": "time"},
            metadata=metadata,
            display_name=time_variable,
        )
        script = self._matlab_function_script_from_expression(expression_text, time_variable=time_variable)
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, "matlab_fcn"),
            "MATLABFunction",
            system=ROOT_SYSTEM,
            name=display_name,
            metadata={**metadata, "matlab_function_script": script},
        )
        self.add_connection(ROOT_SYSTEM, time_ref, block_id, 1, label=time_variable)
        return (block_id, "1")

    def _matlab_function_script_from_expression(self, expression_text: str, *, time_variable: str) -> str:
        return "\n".join(
            [
                f"function y = fcn({time_variable})",
                f"y = {expression_text};",
            ]
        )

    def _native_constant_source(
        self,
        symbol_name: str,
        value: float,
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, "const"),
            "Constant",
            system=ROOT_SYSTEM,
            name=display_name,
            params={"Value": _numeric_string(value)},
            metadata=metadata,
        )
        return (block_id, "1")

    def _combine_native_sources(
        self,
        symbol_name: str,
        kind: str,
        sources: list[tuple[str, str]],
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        if len(sources) == 1:
            return sources[0]
        block_type = "Sum" if kind == "sum" else "Product"
        inputs_param = ("+" if kind == "sum" else "*") * len(sources)
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, kind),
            block_type,
            system=ROOT_SYSTEM,
            name=display_name,
            params={"Inputs": inputs_param},
            metadata=metadata,
        )
        for index, source in enumerate(sources, start=1):
            self.add_connection(ROOT_SYSTEM, source, block_id, index, label=display_name)
        return (block_id, "1")

    def _apply_native_unary_block(
        self,
        symbol_name: str,
        block_type: str,
        source: tuple[str, str],
        *,
        metadata: dict[str, object],
        display_name: str,
        prefix: str,
        params: dict[str, object] | None = None,
    ) -> tuple[str, str]:
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, prefix),
            block_type,
            system=ROOT_SYSTEM,
            name=display_name,
            params=params,
            metadata=metadata,
        )
        self.add_connection(ROOT_SYSTEM, source, block_id, 1, label=display_name)
        return (block_id, "1")

    def _apply_native_gain(
        self,
        symbol_name: str,
        source: tuple[str, str],
        *,
        gain: float,
        metadata: dict[str, object],
        display_name: str,
        prefix: str,
    ) -> tuple[str, str]:
        if math.isclose(gain, 1.0, rel_tol=0.0, abs_tol=1e-12):
            return source
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, prefix),
            "Gain",
            system=ROOT_SYSTEM,
            name=display_name,
            params={"Gain": _numeric_string(gain)},
            metadata=metadata,
        )
        self.add_connection(ROOT_SYSTEM, source, block_id, 1, label=display_name)
        return (block_id, "1")

    def _apply_native_bias(
        self,
        symbol_name: str,
        source: tuple[str, str],
        *,
        bias: float,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        if math.isclose(bias, 0.0, rel_tol=0.0, abs_tol=1e-12):
            return source
        bias_ref = self._native_constant_source(
            symbol_name,
            bias,
            metadata=metadata,
            display_name=f"{display_name}_bias",
        )
        return self._combine_native_sources(
            symbol_name,
            "sum",
            [source, bias_ref],
            metadata=metadata,
            display_name=display_name,
        )

    def _apply_native_delay(
        self,
        symbol_name: str,
        source: tuple[str, str],
        *,
        delay_time: float,
        initial_output: float,
        metadata: dict[str, object],
        display_name: str,
        prefix: str,
    ) -> tuple[str, str]:
        if math.isclose(delay_time, 0.0, rel_tol=0.0, abs_tol=1e-12):
            return source
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, prefix),
            "TransportDelay",
            system=ROOT_SYSTEM,
            name=display_name,
            params={
                "DelayTime": _numeric_string(delay_time),
                "InitialOutput": _numeric_string(initial_output),
            },
            metadata=metadata,
        )
        self.add_connection(ROOT_SYSTEM, source, block_id, 1, label=display_name)
        return (block_id, "1")

    def _build_power_native_source(
        self,
        symbol_name: str,
        source: tuple[str, str],
        *,
        exponent: float,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        if math.isclose(exponent, 0.0, rel_tol=0.0, abs_tol=1e-12):
            return self._native_constant_source(symbol_name, 1.0, metadata=metadata, display_name=display_name)
        if math.isclose(exponent, 1.0, rel_tol=0.0, abs_tol=1e-12):
            return source
        rounded = int(round(exponent))
        if math.isclose(exponent, rounded, rel_tol=0.0, abs_tol=1e-12) and rounded > 1:
            return self._combine_native_sources(
                symbol_name,
                "product",
                [source for _ in range(rounded)],
                metadata=metadata,
                display_name=display_name,
            )
        if math.isclose(exponent, 0.5, rel_tol=0.0, abs_tol=1e-12):
            return self._apply_native_unary_block(
                symbol_name,
                "MathFunction",
                source,
                metadata=metadata,
                display_name=display_name,
                prefix="sqrt",
                params={"Operator": "sqrt"},
            )
        log_ref = self._apply_native_unary_block(
            symbol_name,
            "MathFunction",
            source,
            metadata=metadata,
            display_name=f"{display_name}_log",
            prefix="log",
            params={"Operator": "log"},
        )
        scaled_ref = self._apply_native_gain(
            symbol_name,
            log_ref,
            gain=exponent,
            metadata=metadata,
            display_name=f"{display_name}_gain",
            prefix="pow_gain",
        )
        return self._apply_native_unary_block(
            symbol_name,
            "MathFunction",
            scaled_ref,
            metadata=metadata,
            display_name=display_name,
            prefix="exp",
            params={"Operator": "exp"},
        )

    def _build_repeating_sequence_source(
        self,
        symbol_name: str,
        spec: dict[str, object],
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        period = self._period_from_frequency(float(spec.get("frequency", 1.0)))
        width = float(spec.get("width", 0.5 if str(spec.get("kind", "")) == "triangle" else 1.0))
        amplitude = float(spec.get("amplitude", 1.0))
        bias = float(spec.get("bias", 0.0))
        times, values = self._repeating_sequence_points(period=period, amplitude=amplitude, bias=bias, width=width)
        block_id = self.add_block(
            self._next_native_input_id(symbol_name, "repeat"),
            "RepeatingSequence",
            system=ROOT_SYSTEM,
            name=display_name,
            params={
                "rep_seq_t": "[" + " ".join(_numeric_string(value) for value in times) + "]",
                "rep_seq_y": "[" + " ".join(_numeric_string(value) for value in values) + "]",
            },
            metadata=metadata,
        )
        return (block_id, "1")

    def _repeating_sequence_points(
        self,
        *,
        period: float,
        amplitude: float,
        bias: float,
        width: float,
    ) -> tuple[list[float], list[float]]:
        normalized_width = min(max(width, 1e-6), 1.0)
        if normalized_width >= 1.0 - 1e-12:
            epsilon = max(period * 1e-6, 1e-6)
            return [0.0, max(period - epsilon, 0.0), period], [bias - amplitude, bias + amplitude, bias - amplitude]
        rise_time = normalized_width * period
        return [0.0, rise_time, period], [bias - amplitude, bias + amplitude, bias - amplitude]

    def _wrap_periodic_phase_delay(
        self,
        symbol_name: str,
        source: tuple[str, str],
        *,
        frequency: float,
        phase: float,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        if math.isclose(phase, 0.0, rel_tol=0.0, abs_tol=1e-12):
            return source
        period = self._period_from_frequency(frequency)
        delay_time = math.fmod((-phase / frequency), period)
        if delay_time < 0.0:
            delay_time += period
        return self._apply_native_delay(
            symbol_name,
            source,
            delay_time=delay_time,
            initial_output=0.0,
            metadata=metadata,
            display_name=display_name,
            prefix="phase_delay",
        )

    def _period_from_frequency(self, frequency: float) -> float:
        if math.isclose(frequency, 0.0, rel_tol=0.0, abs_tol=1e-12):
            raise DeterministicCompileError("Native periodic input frequency must be non-zero.")
        return abs((2.0 * math.pi) / frequency)

    def _build_native_piecewise_source(
        self,
        symbol_name: str,
        spec: dict[str, object],
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        branches = spec.get("branches")
        otherwise = spec.get("otherwise")
        if not isinstance(branches, list) or not branches or not isinstance(otherwise, dict):
            raise DeterministicCompileError(f"Native piecewise input spec for {symbol_name!r} is incomplete.")
        current_ref = self._build_native_input_source(
            symbol_name,
            otherwise,
            metadata=metadata,
            display_name=f"{display_name}_otherwise",
        )
        total = len(branches)
        for index, branch in enumerate(reversed(branches), start=1):
            condition_ref = self._build_native_condition_source(
                symbol_name,
                branch.get("condition"),
                metadata=metadata,
                display_name=f"{display_name}_cond_{index}",
            )
            value_spec = branch.get("value")
            if not isinstance(value_spec, dict):
                raise DeterministicCompileError(f"Native piecewise branch for {symbol_name!r} requires a 'value' source.")
            true_ref = self._build_native_input_source(
                symbol_name,
                value_spec,
                metadata=metadata,
                display_name=f"{display_name}_branch_{index}",
            )
            switch_id = self.add_block(
                self._next_native_input_id(symbol_name, "switch"),
                "Switch",
                system=ROOT_SYSTEM,
                name=display_name if index == total else f"{display_name}_switch_{index}",
                params={"Criteria": "u2 >= Threshold", "Threshold": "0.5"},
                metadata=metadata,
            )
            self.add_connection(ROOT_SYSTEM, true_ref, switch_id, 1, label=display_name)
            self.add_connection(ROOT_SYSTEM, condition_ref, switch_id, 2, label=display_name)
            self.add_connection(ROOT_SYSTEM, current_ref, switch_id, 3, label=display_name)
            current_ref = (switch_id, "1")
        return current_ref

    def _build_native_condition_source(
        self,
        symbol_name: str,
        condition: object,
        *,
        metadata: dict[str, object],
        display_name: str,
    ) -> tuple[str, str]:
        if not isinstance(condition, dict):
            raise DeterministicCompileError(f"Native condition for {symbol_name!r} must be an object.")
        kind = str(condition.get("kind", ""))
        if kind == "boolean":
            return self._native_constant_source(
                symbol_name,
                1.0 if bool(condition.get("value", False)) else 0.0,
                metadata=metadata,
                display_name=display_name,
            )
        if kind == "compare":
            lhs = condition.get("lhs")
            rhs = condition.get("rhs")
            if not isinstance(lhs, dict) or not isinstance(rhs, dict):
                raise DeterministicCompileError(f"Native compare condition for {symbol_name!r} requires 'lhs' and 'rhs'.")
            lhs_ref = self._build_native_input_source(symbol_name, lhs, metadata=metadata, display_name=f"{display_name}_lhs")
            rhs_ref = self._build_native_input_source(symbol_name, rhs, metadata=metadata, display_name=f"{display_name}_rhs")
            operator = str(condition.get("op", ""))
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "relop"),
                "RelationalOperator",
                system=ROOT_SYSTEM,
                name=display_name,
                params={"Operator": "~=" if operator == "!=" else operator},
                metadata=metadata,
            )
            self.add_connection(ROOT_SYSTEM, lhs_ref, block_id, 1, label=display_name)
            self.add_connection(ROOT_SYSTEM, rhs_ref, block_id, 2, label=display_name)
            return (block_id, "1")
        if kind in {"and", "or"}:
            terms = condition.get("terms")
            if not isinstance(terms, list) or not terms:
                raise DeterministicCompileError(f"Native {kind} condition for {symbol_name!r} requires terms.")
            term_refs = [
                self._build_native_condition_source(
                    symbol_name,
                    term,
                    metadata=metadata,
                    display_name=f"{display_name}_{index + 1}",
                )
                for index, term in enumerate(terms)
            ]
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, f"logic_{kind}"),
                "LogicOperator",
                system=ROOT_SYSTEM,
                name=display_name,
                params={"Operator": kind.upper(), "Inputs": str(len(term_refs))},
                metadata=metadata,
            )
            for index, term_ref in enumerate(term_refs, start=1):
                self.add_connection(ROOT_SYSTEM, term_ref, block_id, index, label=display_name)
            return (block_id, "1")
        if kind == "not":
            inner_ref = self._build_native_condition_source(
                symbol_name,
                condition.get("input"),
                metadata=metadata,
                display_name=f"{display_name}_inner",
            )
            block_id = self.add_block(
                self._next_native_input_id(symbol_name, "logic_not"),
                "LogicOperator",
                system=ROOT_SYSTEM,
                name=display_name,
                params={"Operator": "NOT"},
                metadata=metadata,
            )
            self.add_connection(ROOT_SYSTEM, inner_ref, block_id, 1, label=display_name)
            return (block_id, "1")
        raise DeterministicCompileError(f"Unsupported native condition kind {kind!r} for {symbol_name!r}.")

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
        input_ids = list(node["inputs"])
        negative_literal_count = sum(1 for child_id in input_ids if self._is_literal_constant_node(child_id, -1.0))
        sign_flip = negative_literal_count % 2 == 1
        if negative_literal_count and len(input_ids) > 1:
            input_ids = [child_id for child_id in input_ids if not self._is_literal_constant_node(child_id, -1.0)]
        if not input_ids:
            return self._materialize_folded_constant_node(node_id, owner=owner, numeric_value=-1.0 if sign_flip else 1.0)

        child_values = [self.numeric_value(child_id) for child_id in input_ids]
        dynamic_children = [child_id for child_id, value in zip(input_ids, child_values) if value is None]
        numeric_symbol_children = [
            child_id
            for child_id, value in zip(input_ids, child_values)
            if value is not None and self._depends_on_symbol_input(child_id)
        ]
        if len(input_ids) == 2 and len(dynamic_children) == 1 and not numeric_symbol_children:
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
            return self._materialize_negation_gain(
                node_id,
                owner=owner,
                upstream=source,
                sign_flip=sign_flip,
                layer_hint=layer_hint,
                layout_role=layout_role,
            )

        block_id = self.add_block(
            f"prod_{node_id}",
            "Product",
            system=owner,
            name=f"prod_{_sanitize_for_id(node_id)}",
            params={"Inputs": "*" * len(input_ids)},
            metadata={
                "layout_role": layout_role,
                "layer_hint": layer_hint,
                "trace_expression": self.node_expressions[node_id],
            },
        )
        raw_source = (block_id, "1")
        for index, child_id in enumerate(input_ids, start=1):
            self.add_connection(
                owner,
                self.resolve_for_system(child_id, owner),
                block_id,
                index,
                label=self.node_expressions[child_id],
            )
        return self._materialize_negation_gain(
            node_id,
            owner=owner,
            upstream=raw_source,
            sign_flip=sign_flip,
            layer_hint=layer_hint,
            layout_role=layout_role,
        )

    def _materialize_division_node(self, node_id: str, *, owner: str) -> tuple[str, str]:
        node = self.node_map[node_id]
        layer_hint, layout_role = self._operator_metadata(node_id, owner=owner)
        numerator_id, denominator_id = node["inputs"]
        denominator_value = self.numeric_value(denominator_id)
        preserve_denominator_symbol = denominator_value is not None and self._depends_on_symbol_input(denominator_id)
        if denominator_value is not None and self.numeric_value(numerator_id) is None and not preserve_denominator_symbol:
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

    def _materialize_negation_gain(
        self,
        node_id: str,
        *,
        owner: str,
        upstream: tuple[str, str],
        sign_flip: bool,
        layer_hint: int,
        layout_role: str,
    ) -> tuple[str, str]:
        if not sign_flip:
            return self._remember_source(node_id, upstream)

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
        self.add_connection(owner, upstream, block_id, 1, label="-1")
        return self._remember_source(node_id, (block_id, "1"))

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

        if op != "integrator" and numeric_value is not None and not self._depends_on_symbol_input(node_id):
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
        return validate_simulink_model_dict(model)


def graph_to_simulink_model(
    graph: dict[str, object],
    *,
    name: str | None = None,
    state_names: list[str] | None = None,
    parameter_values: dict[str, float] | None = None,
    input_values: dict[str, float] | None = None,
    input_specs: dict[str, dict[str, object]] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    initial_conditions: dict[str, float] | None = None,
    algebraic_initial_conditions: dict[str, float] | None = None,
    model_params: dict[str, object] | None = None,
    input_mode: str = "constant",
    layout_mode: LayoutMode = "deterministic",
    visual_repair_config: VisualRepairConfig | None = None,
    openai_client=None,
) -> BackendSimulinkModelDict:
    """Lower a validated graph dictionary into a hierarchical Simulink-ready model dictionary."""
    symbol_values = dict(parameter_values or {})
    symbol_values.update(input_values or {})
    lowerer = GraphToSimulinkLowerer(
        graph=graph,
        model_name=name or f"{graph['name']}_simulink",
        symbol_values=symbol_values,
        input_specs=normalize_input_specs(input_specs=input_specs or {}),
        input_signals=dict(input_signals or {}),
        initial_conditions=dict(initial_conditions or {}),
        algebraic_initial_conditions=dict(algebraic_initial_conditions or {}),
        input_mode=input_mode,
    )
    model = lowerer.lower(state_names=state_names, model_params=model_params)
    return apply_layout_workflow(
        model,
        layout_mode=layout_mode,
        visual_repair_config=visual_repair_config,
        openai_client=openai_client,
    )
