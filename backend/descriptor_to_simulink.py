"""Deterministic lowering from linear descriptor systems to Simulink model dictionaries."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import sympy

from backend.block_library import BLOCK_LIBRARY
from backend.layout_visual_corrector import VisualRepairConfig
from backend.layout_workflow import LayoutMode, apply_layout_workflow
from backend.simulink_dict import BackendSimulinkModelDict, ROOT_SYSTEM, validate_simulink_model_dict
from ir.equation_dict import matrix_from_dict
from latex_frontend.symbols import DeterministicCompileError, RECIPROCAL_FUNCTION_BASES
from simulate.input_specs import normalize_input_specs
from simulink.utils import sanitize_block_name


def _sanitize(name: str) -> str:
    return sanitize_block_name(name)


def _numeric_string(value: sympy.Expr) -> str:
    simplified = sympy.simplify(value)
    if simplified.is_Integer:
        return str(int(simplified))
    return sympy.sstr(simplified)


def _float_string(value: float) -> str:
    if float(value).is_integer():
        return str(int(round(float(value))))
    return repr(float(value))


def _matrix_signal_literal(time_values: list[float], sample_values: list[float]) -> str:
    rows = [
        f"{repr(float(time_value))} {repr(float(sample_value))}"
        for time_value, sample_value in zip(time_values, sample_values)
    ]
    return "[" + "; ".join(rows) + "]"


@dataclass
class DescriptorToSimulinkLowerer:
    descriptor_system: dict[str, object]
    model_name: str
    parameter_values: dict[str, float] = field(default_factory=dict)
    input_values: dict[str, float] = field(default_factory=dict)
    input_specs: dict[str, dict[str, object]] = field(default_factory=dict)
    input_signals: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    differential_initial_conditions: dict[str, float] = field(default_factory=dict)
    algebraic_initial_conditions: dict[str, float] = field(default_factory=dict)
    blocks: dict[str, dict[str, object]] = field(default_factory=dict)
    connections: list[dict[str, object]] = field(default_factory=list)
    workspace_variables: dict[str, object] = field(default_factory=dict)
    sources: dict[str, tuple[str, str]] = field(default_factory=dict)
    counter: int = 0

    def __post_init__(self) -> None:
        if self.descriptor_system.get("form") != "linear_descriptor":
            raise DeterministicCompileError("Descriptor lowering requires a linear_descriptor system.")

        self.differential_states = list(self.descriptor_system["differential_states"])  # type: ignore[index]
        self.algebraic_variables = list(self.descriptor_system["algebraic_variables"])  # type: ignore[index]
        self.variables = list(self.descriptor_system["variables"])  # type: ignore[index]
        self.inputs = list(self.descriptor_system["inputs"])  # type: ignore[index]
        self.independent_variable = self.descriptor_system.get("independent_variable")

        substitutions = {
            sympy.Symbol(name): sympy.Float(float(value))
            for name, value in self.parameter_values.items()
        }
        self.E = self._substitute_matrix(matrix_from_dict(self.descriptor_system["E"]), substitutions)  # type: ignore[arg-type]
        self.A = self._substitute_matrix(matrix_from_dict(self.descriptor_system["A"]), substitutions)  # type: ignore[arg-type]
        self.B = self._substitute_matrix(matrix_from_dict(self.descriptor_system["B"]), substitutions)  # type: ignore[arg-type]
        self.offset = self._substitute_matrix(matrix_from_dict(self.descriptor_system["offset"]), substitutions)  # type: ignore[arg-type]

        self._validate_descriptor_shape()
        self._validate_coefficients()
        self.algebraic_row_assignment = self._match_algebraic_rows()

    def _next_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}_{self.counter:04d}"

    def _substitute_matrix(self, matrix: sympy.Matrix, substitutions: dict[sympy.Symbol, sympy.Expr]) -> sympy.Matrix:
        return sympy.Matrix(
            [
                [sympy.simplify(matrix[row, col].subs(substitutions, simultaneous=True)) for col in range(matrix.cols)]
                for row in range(matrix.rows)
            ]
        )

    def _validate_descriptor_shape(self) -> None:
        equation_count = len(self.variables)
        if self.E.rows != equation_count or self.A.rows != equation_count:
            raise DeterministicCompileError("Descriptor system must have one equation row per variable.")
        if self.E.cols != len(self.variables):
            raise DeterministicCompileError("Descriptor E matrix width must match total variable count.")
        if self.A.cols != len(self.variables):
            raise DeterministicCompileError("Descriptor A matrix width must match total variable count.")
        if self.B.rows != equation_count:
            raise DeterministicCompileError("Descriptor B matrix row count must match equation count.")
        if self.offset.rows != equation_count or self.offset.cols != 1:
            raise DeterministicCompileError("Descriptor offset must be a column vector with one entry per equation.")

    def _validate_coefficients(self) -> None:
        allowed_symbols = set()
        if self.independent_variable is not None:
            allowed_symbols.add(str(self.independent_variable))
        for matrix_name, matrix in [("E", self.E), ("A", self.A), ("B", self.B), ("offset", self.offset)]:
            for entry in matrix:
                unresolved = sorted(symbol.name for symbol in entry.free_symbols if symbol.name not in allowed_symbols)
                if unresolved:
                    raise DeterministicCompileError(
                        f"Descriptor {matrix_name} retains unsupported symbolic coefficients: {unresolved}."
                    )
        if self.independent_variable is not None:
            raise DeterministicCompileError(
                "Descriptor-to-Simulink lowering currently supports time-invariant descriptor systems only."
            )

    def _match_algebraic_rows(self) -> dict[int, int]:
        row_count = len(self.algebraic_variables)
        if row_count == 0:
            return {}

        row_indices = list(range(len(self.differential_states), len(self.variables)))
        col_indices = list(range(len(self.differential_states), len(self.variables)))
        adjacency: dict[int, list[int]] = {}
        for row_position, row_index in enumerate(row_indices):
            adjacency[row_position] = [
                col_position
                for col_position, col_index in enumerate(col_indices)
                if sympy.simplify(self.A[row_index, col_index]) != 0
            ]

        matches: dict[int, int] = {}

        def _assign(row_position: int, seen: set[int]) -> bool:
            for col_position in adjacency[row_position]:
                if col_position in seen:
                    continue
                seen.add(col_position)
                current_row = matches.get(col_position)
                if current_row is None or _assign(current_row, seen):
                    matches[col_position] = row_position
                    return True
            return False

        for row_position in range(row_count):
            if not _assign(row_position, set()):
                raise DeterministicCompileError(
                    "Descriptor algebraic subsystem lacks a deterministic row-to-variable assignment."
                )

        assignment: dict[int, int] = {}
        for col_position, row_position in matches.items():
            assignment[col_indices[col_position]] = row_indices[row_position]
        return assignment

    def add_block(
        self,
        block_id: str,
        block_type: str,
        *,
        name: str,
        params: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        if block_id not in self.blocks:
            self.blocks[block_id] = {
                "type": block_type,
                "lib_path": BLOCK_LIBRARY[block_type]["path"],
                "system": ROOT_SYSTEM,
                "name": name,
                "params": dict(params or {}),
                "metadata": dict(metadata or {}),
            }
        return block_id

    def add_connection(
        self,
        src: tuple[str, str],
        dst_block: str,
        dst_port: int,
        *,
        label: str,
    ) -> None:
        self.connections.append(
            {
                "system": ROOT_SYSTEM,
                "src_block": src[0],
                "src_port": src[1],
                "dst_block": dst_block,
                "dst_port": str(dst_port),
                "label": label,
                "metadata": {},
            }
        )

    def _constant_source(self, value: sympy.Expr, *, name: str, layer_hint: int) -> tuple[str, str]:
        block_id = self.add_block(
            self._next_id("const"),
            "Constant",
            name=name,
            params={"Value": _numeric_string(value)},
            metadata={"layout_role": "shared", "layer_hint": layer_hint, "trace_expression": _numeric_string(value)},
        )
        return (block_id, "1")

    def _native_input_source(self, input_name: str, *, layer_hint: int) -> tuple[str, str] | None:
        spec = self.input_specs.get(input_name)
        if spec is None:
            return None
        metadata = {"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name}
        if not self._is_supported_native_input_spec(spec):
            return None
        return self._build_native_input_source(input_name, spec, layer_hint=layer_hint, display_name=input_name, metadata=metadata)

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

    def _build_native_input_source(
        self,
        input_name: str,
        spec: dict[str, object],
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        kind = str(spec.get("kind", ""))
        if kind == "constant":
            return self._native_constant_source(
                input_name,
                float(spec.get("value", 0.0)),
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "time":
            block_id = self.add_block(
                self._next_id("input_time"),
                "Clock",
                name=display_name,
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "step":
            bias = float(spec.get("bias", 0.0))
            amplitude = float(spec.get("amplitude", 1.0))
            block_id = self.add_block(
                self._next_id("input_step"),
                "Step",
                name=display_name,
                params={
                    "Time": _float_string(float(spec.get("start_time", 0.0))),
                    "Before": _float_string(bias),
                    "After": _float_string(bias + amplitude),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "square":
            sine_ref = self._build_native_input_source(
                input_name,
                {
                    "kind": "sine",
                    "amplitude": 1.0,
                    "frequency": float(spec.get("frequency", 1.0)),
                    "phase": float(spec.get("phase", 0.0)),
                    "bias": 0.0,
                },
                layer_hint=layer_hint,
                display_name=f"{display_name}_src",
                metadata=metadata,
            )
            sign_ref = self._apply_native_unary_block(
                input_name,
                "Sign",
                sine_ref,
                layer_hint=layer_hint,
                display_name=f"{display_name}_sign",
                metadata=metadata,
                prefix="input_sign",
            )
            scaled_ref = self._apply_native_gain_to_source(
                input_name,
                sign_ref,
                gain=float(spec.get("amplitude", 1.0)),
                layer_hint=layer_hint,
                display_name=f"{display_name}_gain",
                metadata=metadata,
                prefix="input_square_gain",
            )
            return self._apply_native_bias(
                input_name,
                scaled_ref,
                bias=float(spec.get("bias", 0.0)),
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind in {"sawtooth", "triangle"}:
            base_ref = self._build_repeating_sequence_source(
                input_name,
                spec,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
            return self._wrap_periodic_phase_delay(
                input_name,
                base_ref,
                frequency=float(spec.get("frequency", 1.0)),
                phase=float(spec.get("phase", 0.0)),
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "ramp":
            block_id = self.add_block(
                self._next_id("input_ramp"),
                "Ramp",
                name=display_name,
                params={
                    "slope": _float_string(float(spec.get("slope", 1.0))),
                    "start": _float_string(float(spec.get("start_time", 0.0))),
                    "InitialOutput": _float_string(float(spec.get("initial_output", 0.0))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind in {"impulse", "pulse"}:
            amplitude = float(spec.get("amplitude", 1.0))
            width = float(spec.get("width", 1.0))
            if width <= 0.0:
                raise DeterministicCompileError(f"Native {kind} width for input {input_name!r} must be positive.")
            period = float(spec.get("period", max(width * 2.0, 1.0)))
            if period <= 0.0:
                raise DeterministicCompileError(f"Native {kind} period for input {input_name!r} must be positive.")
            pulse_amplitude = amplitude / width if kind == "impulse" else amplitude
            bias = float(spec.get("bias", 0.0))
            pulse_id = self.add_block(
                self._next_id(f"input_{kind}"),
                "PulseGenerator",
                name=display_name if abs(bias) <= 1e-12 else f"{display_name}_{kind}",
                params={
                    "PulseType": "Time based",
                    "Amplitude": _float_string(pulse_amplitude),
                    "Period": _float_string(period),
                    "PulseWidth": _float_string(100.0 * width / period),
                    "PhaseDelay": _float_string(float(spec.get("start_time", 0.0))),
                },
                metadata=metadata,
            )
            pulse_ref = (pulse_id, "1")
            if abs(bias) <= 1e-12:
                return pulse_ref
            bias_ref = self._build_native_input_source(
                input_name,
                {"kind": "constant", "value": bias},
                layer_hint=layer_hint,
                display_name=f"{display_name}_bias",
                metadata=metadata,
            )
            return self._combine_native_sources(
                input_name,
                "sum",
                [bias_ref, pulse_ref],
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "sine":
            block_id = self.add_block(
                self._next_id("input_sine"),
                "SineWave",
                name=display_name,
                params={
                    "Amplitude": _float_string(float(spec.get("amplitude", 1.0))),
                    "Frequency": _float_string(float(spec.get("frequency", 1.0))),
                    "Phase": _float_string(float(spec.get("phase", 0.0))),
                    "Bias": _float_string(float(spec.get("bias", 0.0))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind in {"sum", "product"}:
            terms = spec.get("terms")
            if not isinstance(terms, list) or not terms:
                raise DeterministicCompileError(
                    f"Native {kind} input spec for {input_name!r} requires a non-empty terms list."
                )
            sources = [
                self._build_native_input_source(
                    input_name,
                    term,
                    layer_hint=layer_hint,
                    display_name=f"{display_name}_term_{index + 1}",
                    metadata=metadata,
                )
                for index, term in enumerate(terms)
            ]
            return self._combine_native_sources(
                input_name,
                kind,
                sources,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "trig_function":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native trig_function input spec for {input_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_arg",
                metadata=metadata,
            )
            return self._apply_native_unary_block(
                input_name,
                "TrigonometricFunction",
                inner_ref,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
                prefix=f"input_trig_{str(spec.get('operator', 'trig')).lower()}",
                params={"Operator": str(spec.get("operator", "")).lower()},
            )
        if kind == "binary_trig_function":
            lhs = spec.get("lhs")
            rhs = spec.get("rhs")
            if not isinstance(lhs, dict) or not isinstance(rhs, dict):
                raise DeterministicCompileError(
                    f"Native binary_trig_function input spec for {input_name!r} requires 'lhs' and 'rhs' sources."
                )
            lhs_ref = self._build_native_input_source(
                input_name,
                lhs,
                layer_hint=layer_hint,
                display_name=f"{display_name}_lhs",
                metadata=metadata,
            )
            rhs_ref = self._build_native_input_source(
                input_name,
                rhs,
                layer_hint=layer_hint,
                display_name=f"{display_name}_rhs",
                metadata=metadata,
            )
            operator = str(spec.get("operator", "")).lower()
            block_id = self.add_block(
                self._next_id(f"input_trig_{operator}"),
                "TrigonometricFunction",
                name=display_name,
                params={"Operator": operator},
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            self.add_connection(lhs_ref, block_id, 1, label=display_name)
            self.add_connection(rhs_ref, block_id, 2, label=display_name)
            return (block_id, "1")
        if kind == "reciprocal_trig_function":
            inner = spec.get("input")
            operator = str(spec.get("operator", "")).lower()
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native reciprocal_trig_function input spec for {input_name!r} requires an 'input' source."
                )
            if operator not in RECIPROCAL_FUNCTION_BASES:
                raise DeterministicCompileError(
                    f"Unsupported reciprocal trig operator {operator!r} for {input_name!r}."
                )
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_arg",
                metadata=metadata,
            )
            trig_ref = self._apply_native_unary_block(
                input_name,
                "TrigonometricFunction",
                inner_ref,
                layer_hint=layer_hint,
                display_name=f"{display_name}_{RECIPROCAL_FUNCTION_BASES[operator]}",
                metadata=metadata,
                prefix=f"input_trig_{RECIPROCAL_FUNCTION_BASES[operator]}",
                params={"Operator": RECIPROCAL_FUNCTION_BASES[operator]},
            )
            one_ref = self._native_constant_source(
                input_name,
                1.0,
                layer_hint=layer_hint,
                display_name=f"{display_name}_one",
                metadata=metadata,
            )
            block_id = self.add_block(
                self._next_id(f"input_recip_{operator}"),
                "Divide",
                name=display_name,
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            self.add_connection(one_ref, block_id, 1, label="1")
            self.add_connection(trig_ref, block_id, 2, label=display_name)
            return (block_id, "1")
        if kind == "math_function":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native math_function input spec for {input_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_arg",
                metadata=metadata,
            )
            return self._apply_native_unary_block(
                input_name,
                "MathFunction",
                inner_ref,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
                prefix=f"input_math_{str(spec.get('operator', 'math')).lower()}",
                params={"Operator": str(spec.get("operator", "")).lower()},
            )
        if kind == "minmax":
            terms = spec.get("terms")
            if not isinstance(terms, list) or not terms:
                raise DeterministicCompileError(
                    f"Native minmax input spec for {input_name!r} requires a non-empty terms list."
                )
            term_refs = [
                self._build_native_input_source(
                    input_name,
                    term,
                    layer_hint=layer_hint,
                    display_name=f"{display_name}_{index + 1}",
                    metadata=metadata,
                )
                for index, term in enumerate(terms)
            ]
            operator = str(spec.get("operator", "")).lower()
            block_id = self.add_block(
                self._next_id(f"input_minmax_{operator}"),
                "MinMax",
                name=display_name,
                params={"Function": operator, "Inputs": str(len(term_refs))},
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            for index, term_ref in enumerate(term_refs, start=1):
                self.add_connection(term_ref, block_id, index, label=display_name)
            return (block_id, "1")
        if kind == "power":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(f"Native power input spec for {input_name!r} requires an 'input' source.")
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_src",
                metadata=metadata,
            )
            return self._build_power_native_source(
                input_name,
                inner_ref,
                exponent=float(spec.get("exponent", 1.0)),
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "exp":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native exponential input spec for {input_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_src",
                metadata=metadata,
            )
            return self._apply_native_unary_block(
                input_name,
                "MathFunction",
                inner_ref,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
                prefix="input_exp",
                params={"Operator": "exp"},
            )
        if kind == "delay":
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(f"Native delay input spec for {input_name!r} requires an 'input' source.")
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_src",
                metadata=metadata,
            )
            return self._apply_native_delay(
                input_name,
                inner_ref,
                delay_time=float(spec.get("delay_time", 0.0)),
                initial_output=float(spec.get("initial_output", 0.0)),
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
                prefix="input_delay",
            )
        if kind in {"saturation", "dead_zone", "abs", "sign", "relay"}:
            inner = spec.get("input")
            if not isinstance(inner, dict):
                raise DeterministicCompileError(
                    f"Native {kind} input spec for {input_name!r} requires an 'input' source."
                )
            inner_ref = self._build_native_input_source(
                input_name,
                inner,
                layer_hint=layer_hint,
                display_name=f"{display_name}_src",
                metadata=metadata,
            )
            if kind == "saturation":
                block_type = "Saturation"
                prefix = "input_sat"
                params = {
                    "LowerLimit": _float_string(float(spec.get("lower_limit", -1.0))),
                    "UpperLimit": _float_string(float(spec.get("upper_limit", 1.0))),
                }
            elif kind == "dead_zone":
                block_type = "DeadZone"
                prefix = "input_deadzone"
                params = {
                    "LowerValue": _float_string(float(spec.get("lower_limit", -1.0))),
                    "UpperValue": _float_string(float(spec.get("upper_limit", 1.0))),
                }
            elif kind == "abs":
                block_type = "Abs"
                prefix = "input_abs"
                params = {}
            elif kind == "sign":
                block_type = "Sign"
                prefix = "input_sign"
                params = {}
            else:
                block_type = "Relay"
                prefix = "input_relay"
                params = {
                    "OnSwitchValue": _float_string(float(spec.get("on_switch_value", 0.0))),
                    "OffSwitchValue": _float_string(float(spec.get("off_switch_value", 0.0))),
                    "OnOutputValue": _float_string(float(spec.get("on_output_value", 1.0))),
                    "OffOutputValue": _float_string(float(spec.get("off_output_value", -1.0))),
                }
            return self._apply_native_unary_block(
                input_name,
                block_type,
                inner_ref,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
                prefix=prefix,
                params=params,
            )
        if kind == "piecewise":
            return self._build_native_piecewise_source(
                input_name,
                spec,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "random_number":
            block_id = self.add_block(
                self._next_id("input_uniform_random"),
                "UniformRandomNumber",
                name=display_name,
                params={
                    "Minimum": _float_string(float(spec.get("minimum", 0.0))),
                    "Maximum": _float_string(float(spec.get("maximum", 1.0))),
                    "Seed": _float_string(float(spec.get("seed", 0.0))),
                    "SampleTime": _float_string(float(spec.get("sample_time", 0.01))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "white_noise":
            block_id = self.add_block(
                self._next_id("input_random"),
                "RandomNumber",
                name=display_name,
                params={
                    "Mean": _float_string(float(spec.get("mean", 0.0))),
                    "Variance": _float_string(float(spec.get("variance", 1.0))),
                    "Seed": _float_string(float(spec.get("seed", 0.0))),
                    "SampleTime": _float_string(float(spec.get("sample_time", 0.01))),
                },
                metadata=metadata,
            )
            return (block_id, "1")
        if kind == "expression":
            return self._build_expression_function_source(
                input_name,
                spec,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        raise DeterministicCompileError(f"Unsupported native input spec kind {kind!r} for input {input_name!r}.")

    def _build_expression_function_source(
        self,
        input_name: str,
        spec: dict[str, object],
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        expression_text = str(spec.get("expression", "")).strip()
        if not expression_text:
            raise DeterministicCompileError(f"Expression input spec for {input_name!r} requires a non-empty expression.")
        time_variable = str(spec.get("time_variable", "t")).strip() or "t"
        time_ref = self._build_native_input_source(
            input_name,
            {"kind": "time"},
            layer_hint=layer_hint,
            display_name=time_variable,
            metadata=metadata,
        )
        block_id = self.add_block(
            self._next_id("input_matlab_function"),
            "MATLABFunction",
            name=display_name,
            metadata={
                "layout_role": "source",
                "layer_hint": layer_hint,
                "trace_expression": input_name,
                **metadata,
                "matlab_function_script": self._matlab_function_script_from_expression(expression_text, time_variable=time_variable),
            },
        )
        self.add_connection(time_ref, block_id, 1, label=time_variable)
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
        input_name: str,
        value: float,
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        block_id = self.add_block(
            self._next_id("input_const"),
            "Constant",
            name=display_name,
            params={"Value": _float_string(value)},
            metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
        )
        return (block_id, "1")

    def _combine_native_sources(
        self,
        input_name: str,
        kind: str,
        sources: list[tuple[str, str]],
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        if len(sources) == 1:
            return sources[0]
        block_type = "Sum" if kind == "sum" else "Product"
        block_id = self.add_block(
            self._next_id(f"input_{kind}"),
            block_type,
            name=display_name,
            params={"Inputs": ("+" if kind == "sum" else "*") * len(sources)},
            metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
        )
        for index, source in enumerate(sources, start=1):
            self.add_connection(source, block_id, index, label=display_name)
        return (block_id, "1")

    def _apply_native_unary_block(
        self,
        input_name: str,
        block_type: str,
        source: tuple[str, str],
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
        prefix: str,
        params: dict[str, object] | None = None,
    ) -> tuple[str, str]:
        block_id = self.add_block(
            self._next_id(prefix),
            block_type,
            name=display_name,
            params=params,
            metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
        )
        self.add_connection(source, block_id, 1, label=display_name)
        return (block_id, "1")

    def _apply_native_gain_to_source(
        self,
        input_name: str,
        source: tuple[str, str],
        *,
        gain: float,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
        prefix: str,
    ) -> tuple[str, str]:
        if abs(gain - 1.0) <= 1e-12:
            return source
        block_id = self.add_block(
            self._next_id(prefix),
            "Gain",
            name=display_name,
            params={"Gain": _float_string(gain)},
            metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
        )
        self.add_connection(source, block_id, 1, label=display_name)
        return (block_id, "1")

    def _apply_native_bias(
        self,
        input_name: str,
        source: tuple[str, str],
        *,
        bias: float,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        if abs(bias) <= 1e-12:
            return source
        bias_ref = self._native_constant_source(
            input_name,
            bias,
            layer_hint=layer_hint,
            display_name=f"{display_name}_bias",
            metadata=metadata,
        )
        return self._combine_native_sources(
            input_name,
            "sum",
            [source, bias_ref],
            layer_hint=layer_hint,
            display_name=display_name,
            metadata=metadata,
        )

    def _apply_native_delay(
        self,
        input_name: str,
        source: tuple[str, str],
        *,
        delay_time: float,
        initial_output: float,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
        prefix: str,
    ) -> tuple[str, str]:
        if abs(delay_time) <= 1e-12:
            return source
        block_id = self.add_block(
            self._next_id(prefix),
            "TransportDelay",
            name=display_name,
            params={"DelayTime": _float_string(delay_time), "InitialOutput": _float_string(initial_output)},
            metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
        )
        self.add_connection(source, block_id, 1, label=display_name)
        return (block_id, "1")

    def _build_power_native_source(
        self,
        input_name: str,
        source: tuple[str, str],
        *,
        exponent: float,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        if abs(exponent) <= 1e-12:
            return self._native_constant_source(input_name, 1.0, layer_hint=layer_hint, display_name=display_name, metadata=metadata)
        if abs(exponent - 1.0) <= 1e-12:
            return source
        rounded = int(round(exponent))
        if abs(exponent - rounded) <= 1e-12 and rounded > 1:
            return self._combine_native_sources(
                input_name,
                "product",
                [source for _ in range(rounded)],
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if abs(exponent - 0.5) <= 1e-12:
            return self._apply_native_unary_block(
                input_name,
                "MathFunction",
                source,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
                prefix="input_sqrt",
                params={"Operator": "sqrt"},
            )
        log_ref = self._apply_native_unary_block(
            input_name,
            "MathFunction",
            source,
            layer_hint=layer_hint,
            display_name=f"{display_name}_log",
            metadata=metadata,
            prefix="input_log",
            params={"Operator": "log"},
        )
        scaled_ref = self._apply_native_gain_to_source(
            input_name,
            log_ref,
            gain=exponent,
            layer_hint=layer_hint,
            display_name=f"{display_name}_gain",
            metadata=metadata,
            prefix="input_pow_gain",
        )
        return self._apply_native_unary_block(
            input_name,
            "MathFunction",
            scaled_ref,
            layer_hint=layer_hint,
            display_name=display_name,
            metadata=metadata,
            prefix="input_exp",
            params={"Operator": "exp"},
        )

    def _build_repeating_sequence_source(
        self,
        input_name: str,
        spec: dict[str, object],
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        period = self._period_from_frequency(float(spec.get("frequency", 1.0)))
        width = float(spec.get("width", 0.5 if str(spec.get("kind", "")) == "triangle" else 1.0))
        amplitude = float(spec.get("amplitude", 1.0))
        bias = float(spec.get("bias", 0.0))
        times, values = self._repeating_sequence_points(period=period, amplitude=amplitude, bias=bias, width=width)
        block_id = self.add_block(
            self._next_id("input_repeat"),
            "RepeatingSequence",
            name=display_name,
            params={
                "rep_seq_t": "[" + " ".join(_float_string(value) for value in times) + "]",
                "rep_seq_y": "[" + " ".join(_float_string(value) for value in values) + "]",
            },
            metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
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
        input_name: str,
        source: tuple[str, str],
        *,
        frequency: float,
        phase: float,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        if abs(phase) <= 1e-12:
            return source
        period = self._period_from_frequency(frequency)
        delay_time = math.fmod((-phase / frequency), period)
        if delay_time < 0.0:
            delay_time += period
        return self._apply_native_delay(
            input_name,
            source,
            delay_time=delay_time,
            initial_output=0.0,
            layer_hint=layer_hint,
            display_name=display_name,
            metadata=metadata,
            prefix="input_phase_delay",
        )

    def _period_from_frequency(self, frequency: float) -> float:
        if abs(frequency) <= 1e-12:
            raise DeterministicCompileError("Native periodic input frequency must be non-zero.")
        return abs((2.0 * math.pi) / frequency)

    def _build_native_piecewise_source(
        self,
        input_name: str,
        spec: dict[str, object],
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        branches = spec.get("branches")
        otherwise = spec.get("otherwise")
        if not isinstance(branches, list) or not branches or not isinstance(otherwise, dict):
            raise DeterministicCompileError(f"Native piecewise input spec for {input_name!r} is incomplete.")
        current_ref = self._build_native_input_source(
            input_name,
            otherwise,
            layer_hint=layer_hint,
            display_name=f"{display_name}_otherwise",
            metadata=metadata,
        )
        total = len(branches)
        for index, branch in enumerate(reversed(branches), start=1):
            condition_ref = self._build_native_condition_source(
                input_name,
                branch.get("condition"),
                layer_hint=layer_hint,
                display_name=f"{display_name}_cond_{index}",
                metadata=metadata,
            )
            value_spec = branch.get("value")
            if not isinstance(value_spec, dict):
                raise DeterministicCompileError(f"Native piecewise branch for {input_name!r} requires a 'value' source.")
            true_ref = self._build_native_input_source(
                input_name,
                value_spec,
                layer_hint=layer_hint,
                display_name=f"{display_name}_branch_{index}",
                metadata=metadata,
            )
            switch_id = self.add_block(
                self._next_id("input_switch"),
                "Switch",
                name=display_name if index == total else f"{display_name}_switch_{index}",
                params={"Criteria": "u2 >= Threshold", "Threshold": "0.5"},
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            self.add_connection(true_ref, switch_id, 1, label=display_name)
            self.add_connection(condition_ref, switch_id, 2, label=display_name)
            self.add_connection(current_ref, switch_id, 3, label=display_name)
            current_ref = (switch_id, "1")
        return current_ref

    def _build_native_condition_source(
        self,
        input_name: str,
        condition: object,
        *,
        layer_hint: int,
        display_name: str,
        metadata: dict[str, object],
    ) -> tuple[str, str]:
        if not isinstance(condition, dict):
            raise DeterministicCompileError(f"Native condition for {input_name!r} must be an object.")
        kind = str(condition.get("kind", ""))
        if kind == "boolean":
            return self._native_constant_source(
                input_name,
                1.0 if bool(condition.get("value", False)) else 0.0,
                layer_hint=layer_hint,
                display_name=display_name,
                metadata=metadata,
            )
        if kind == "compare":
            lhs = condition.get("lhs")
            rhs = condition.get("rhs")
            if not isinstance(lhs, dict) or not isinstance(rhs, dict):
                raise DeterministicCompileError(f"Native compare condition for {input_name!r} requires 'lhs' and 'rhs'.")
            lhs_ref = self._build_native_input_source(input_name, lhs, layer_hint=layer_hint, display_name=f"{display_name}_lhs", metadata=metadata)
            rhs_ref = self._build_native_input_source(input_name, rhs, layer_hint=layer_hint, display_name=f"{display_name}_rhs", metadata=metadata)
            operator = str(condition.get("op", ""))
            block_id = self.add_block(
                self._next_id("input_relop"),
                "RelationalOperator",
                name=display_name,
                params={"Operator": "~=" if operator == "!=" else operator},
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            self.add_connection(lhs_ref, block_id, 1, label=display_name)
            self.add_connection(rhs_ref, block_id, 2, label=display_name)
            return (block_id, "1")
        if kind in {"and", "or"}:
            terms = condition.get("terms")
            if not isinstance(terms, list) or not terms:
                raise DeterministicCompileError(f"Native {kind} condition for {input_name!r} requires terms.")
            term_refs = [
                self._build_native_condition_source(
                    input_name,
                    term,
                    layer_hint=layer_hint,
                    display_name=f"{display_name}_{index + 1}",
                    metadata=metadata,
                )
                for index, term in enumerate(terms)
            ]
            block_id = self.add_block(
                self._next_id("input_logic"),
                "LogicOperator",
                name=display_name,
                params={"Operator": kind.upper(), "Inputs": str(len(term_refs))},
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            for index, term_ref in enumerate(term_refs, start=1):
                self.add_connection(term_ref, block_id, index, label=display_name)
            return (block_id, "1")
        if kind == "not":
            inner_ref = self._build_native_condition_source(
                input_name,
                condition.get("input"),
                layer_hint=layer_hint,
                display_name=f"{display_name}_inner",
                metadata=metadata,
            )
            block_id = self.add_block(
                self._next_id("input_logic_not"),
                "LogicOperator",
                name=display_name,
                params={"Operator": "NOT"},
                metadata={"layout_role": "source", "layer_hint": layer_hint, "trace_expression": input_name, **metadata},
            )
            self.add_connection(inner_ref, block_id, 1, label=display_name)
            return (block_id, "1")
        raise DeterministicCompileError(f"Unsupported native condition kind {kind!r} for {input_name!r}.")

    def _apply_gain(self, source: tuple[str, str], coefficient: sympy.Expr, *, trace: str, layer_hint: int) -> tuple[str, str]:
        simplified = sympy.simplify(coefficient)
        if simplified == 1:
            return source
        block_id = self.add_block(
            self._next_id("gain"),
            "Gain",
            name=f"gain_{_sanitize(trace)}",
            params={"Gain": _numeric_string(simplified)},
            metadata={"layout_role": "shared", "layer_hint": layer_hint, "trace_expression": f"{_numeric_string(simplified)}*{trace}"},
        )
        self.add_connection(source, block_id, 1, label=trace)
        return (block_id, "1")

    def _sum_terms(
        self,
        terms: list[tuple[tuple[str, str], str]],
        *,
        trace_expression: str,
        layer_hint: int,
    ) -> tuple[str, str]:
        if not terms:
            return self._constant_source(sympy.Integer(0), name="zero", layer_hint=layer_hint)
        if len(terms) == 1:
            return terms[0][0]
        block_id = self.add_block(
            self._next_id("sum"),
            "Sum",
            name=f"sum_{self.counter}",
            params={"Inputs": "+" * len(terms)},
            metadata={"layout_role": "shared", "layer_hint": layer_hint, "trace_expression": trace_expression},
        )
        for index, (source, label) in enumerate(terms, start=1):
            self.add_connection(source, block_id, index, label=label)
        return (block_id, "1")

    def _build_linear_combination(
        self,
        *,
        variable_coefficients: list[tuple[str, sympy.Expr]],
        input_coefficients: list[tuple[str, sympy.Expr]],
        constant_term: sympy.Expr,
        trace_expression: str,
        layer_hint: int,
    ) -> tuple[str, str]:
        terms: list[tuple[tuple[str, str], str]] = []
        for variable_name, coefficient in variable_coefficients:
            simplified = sympy.simplify(coefficient)
            if simplified == 0:
                continue
            source = self._apply_gain(
                self.sources[variable_name],
                simplified,
                trace=variable_name,
                layer_hint=layer_hint,
            )
            terms.append((source, f"{_numeric_string(simplified)}*{variable_name}" if simplified != 1 else variable_name))
        for input_name, coefficient in input_coefficients:
            simplified = sympy.simplify(coefficient)
            if simplified == 0:
                continue
            source = self._apply_gain(
                self.sources[input_name],
                simplified,
                trace=input_name,
                layer_hint=layer_hint,
            )
            terms.append((source, f"{_numeric_string(simplified)}*{input_name}" if simplified != 1 else input_name))
        constant_simplified = sympy.simplify(constant_term)
        if constant_simplified != 0:
            const_source = self._constant_source(
                constant_simplified,
                name=f"const_{self.counter}",
                layer_hint=layer_hint,
            )
            terms.append((const_source, _numeric_string(constant_simplified)))
        return self._sum_terms(terms, trace_expression=trace_expression, layer_hint=layer_hint)

    def _materialize_inputs(self) -> None:
        for input_name in self.inputs:
            metadata = {"layout_role": "source", "layer_hint": 0, "trace_expression": input_name}
            native_source = self._native_input_source(input_name, layer_hint=0)
            if native_source is not None:
                self.sources[input_name] = native_source
                continue
            if input_name in self.input_signals:
                series = self.input_signals[input_name]
                block_id = self.add_block(
                    f"input_{_sanitize(input_name)}",
                    "FromWorkspace",
                    name=input_name,
                    params={"VariableName": _matrix_signal_literal(list(series["time"]), list(series["values"]))},
                    metadata=metadata,
                )
            elif input_name in self.input_values:
                block_id = self.add_block(
                    f"input_{_sanitize(input_name)}",
                    "Constant",
                    name=input_name,
                    params={"Value": _numeric_string(sympy.Float(float(self.input_values[input_name])))},
                    metadata=metadata,
                )
            else:
                raise DeterministicCompileError(
                    f"No numeric value or input signal provided for descriptor input {input_name!r}."
                )
            self.sources[input_name] = (block_id, "1")

    def _materialize_differential_states(self) -> None:
        for index, state in enumerate(self.differential_states):
            params: dict[str, object] = {}
            if state in self.differential_initial_conditions:
                params["InitialCondition"] = _numeric_string(sympy.Float(float(self.differential_initial_conditions[state])))
            block_id = self.add_block(
                f"int_{_sanitize(state)}",
                "Integrator",
                name=state,
                params=params,
                metadata={"layout_role": "shared", "layer_hint": 4 + index, "trace_expression": state, "state_order": 0},
            )
            self.sources[state] = (block_id, "1")

    def _materialize_algebraic_variables(self) -> None:
        for index, variable in enumerate(self.algebraic_variables):
            params: dict[str, object] = {}
            if variable in self.algebraic_initial_conditions:
                params["InitialGuess"] = _numeric_string(sympy.Float(float(self.algebraic_initial_conditions[variable])))
            block_id = self.add_block(
                f"alg_{_sanitize(variable)}",
                "AlgebraicConstraint",
                name=variable,
                params=params,
                metadata={"layout_role": "shared", "layer_hint": 3 + index, "trace_expression": variable},
            )
            self.sources[variable] = (block_id, "1")

    def _build_differential_rhs(self) -> None:
        for row_index, state in enumerate(self.differential_states):
            derivative_coefficients = [sympy.simplify(self.E[row_index, column]) for column in range(self.E.cols)]
            nonzero_positions = [index for index, coefficient in enumerate(derivative_coefficients) if coefficient != 0]
            if nonzero_positions != [row_index]:
                raise DeterministicCompileError(
                    "Descriptor differential rows must isolate the matching state derivative deterministically."
                )
            scale = sympy.simplify(derivative_coefficients[row_index])
            variable_coefficients = [
                (variable, sympy.simplify(self.A[row_index, column] / scale))
                for column, variable in enumerate(self.variables)
            ]
            input_coefficients = [
                (input_name, sympy.simplify(self.B[row_index, column] / scale))
                for column, input_name in enumerate(self.inputs)
            ]
            rhs_source = self._build_linear_combination(
                variable_coefficients=variable_coefficients,
                input_coefficients=input_coefficients,
                constant_term=sympy.simplify(self.offset[row_index, 0] / scale),
                trace_expression=f"d/dt {state}",
                layer_hint=2,
            )
            self.add_connection(rhs_source, self.sources[state][0], 1, label=f"d/dt {state}")

    def _build_algebraic_constraints(self) -> None:
        if not self.algebraic_variables:
            return
        for algebraic_index, variable in enumerate(self.algebraic_variables):
            variable_column = len(self.differential_states) + algebraic_index
            row_index = self.algebraic_row_assignment[variable_column]
            variable_coefficients = [
                (name, sympy.simplify(self.A[row_index, column]))
                for column, name in enumerate(self.variables)
            ]
            input_coefficients = [
                (input_name, sympy.simplify(self.B[row_index, column]))
                for column, input_name in enumerate(self.inputs)
            ]
            residual_source = self._build_linear_combination(
                variable_coefficients=variable_coefficients,
                input_coefficients=input_coefficients,
                constant_term=sympy.simplify(self.offset[row_index, 0]),
                trace_expression=f"constraint_{variable}",
                layer_hint=1,
            )
            self.add_connection(residual_source, self.sources[variable][0], 1, label=f"0 = constraint_{variable}")

    def lower(
        self,
        *,
        output_names: list[str] | None = None,
        model_params: dict[str, object] | None = None,
    ) -> BackendSimulinkModelDict:
        self._materialize_inputs()
        self._materialize_differential_states()
        self._materialize_algebraic_variables()
        self._build_algebraic_constraints()
        self._build_differential_rhs()

        outputs: list[dict[str, str]] = []
        names = output_names or [*self.differential_states, *self.algebraic_variables]
        for index, name in enumerate(names, start=1):
            if name not in self.sources:
                raise DeterministicCompileError(f"Descriptor output {name!r} is not available.")
            out_block = self.add_block(
                f"out_{_sanitize(name)}",
                "Outport",
                name=f"out_{name}",
                params={"Port": index},
                metadata={"layout_role": "output", "trace_expression": name},
            )
            self.add_connection(self.sources[name], out_block, 1, label=name)
            outputs.append({"name": name, "block": out_block, "port": "1"})

        model = validate_simulink_model_dict(
            {
                "name": self.model_name,
                "blocks": self.blocks,
                "connections": self.connections,
                "outputs": outputs,
                "model_params": dict(model_params or {}),
                "workspace_variables": dict(self.workspace_variables),
                "metadata": {
                    "descriptor_form": self.descriptor_system.get("form"),
                    "differential_states": list(self.differential_states),
                    "algebraic_variables": list(self.algebraic_variables),
                },
            }
        )
        return validate_simulink_model_dict(model)


def descriptor_to_simulink_model(
    descriptor_system: dict[str, object],
    *,
    name: str,
    parameter_values: dict[str, float] | None = None,
    input_values: dict[str, float] | None = None,
    input_specs: dict[str, dict[str, object]] | None = None,
    input_signals: dict[str, dict[str, list[float]]] | None = None,
    differential_initial_conditions: dict[str, float] | None = None,
    algebraic_initial_conditions: dict[str, float] | None = None,
    output_names: list[str] | None = None,
    model_params: dict[str, object] | None = None,
    layout_mode: LayoutMode = "deterministic",
    visual_repair_config: VisualRepairConfig | None = None,
    openai_client=None,
) -> BackendSimulinkModelDict:
    """Lower a linear descriptor system into a Simulink-ready model dictionary."""
    lowerer = DescriptorToSimulinkLowerer(
        descriptor_system=descriptor_system,
        model_name=name,
        parameter_values=dict(parameter_values or {}),
        input_values=dict(input_values or {}),
        input_specs=normalize_input_specs(input_specs=input_specs or {}),
        input_signals=dict(input_signals or {}),
        differential_initial_conditions=dict(differential_initial_conditions or {}),
        algebraic_initial_conditions=dict(algebraic_initial_conditions or {}),
    )
    model = lowerer.lower(output_names=output_names, model_params=model_params)
    return apply_layout_workflow(
        model,
        layout_mode=layout_mode,
        visual_repair_config=visual_repair_config,
        openai_client=openai_client,
    )
