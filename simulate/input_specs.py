"""Helpers for building runtime input functions from lightweight specs."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping

import sympy
from sympy.core.relational import Relational
from sympy.parsing.sympy_parser import convert_xor, parse_expr, standard_transformations

from ir.equation_dict import sympy_function_locals
from latex_frontend.symbols import (
    DeterministicCompileError,
    DIRECT_SIMULINK_BINARY_TRIG_FUNCTIONS,
    DIRECT_SIMULINK_MATH_FUNCTIONS,
    DIRECT_SIMULINK_MINMAX_FUNCTIONS,
    DIRECT_SIMULINK_TRIG_FUNCTIONS,
    RECIPROCAL_FUNCTION_BASES,
)
from simulate.ode_sim import InputFunction, constant_inputs

_PARSE_TRANSFORMATIONS = standard_transformations + (convert_xor,)
_INPUT_SPEC_LOCALS = sympy_function_locals()
_SAWTOOTH_FUNCTION = sympy.Function("sawtooth")
_RAND_FUNCTION = sympy.Function("rand")
_RANDN_FUNCTION = sympy.Function("randn")
_INPUT_SPEC_LOCALS.update(
    {
        "heaviside": sympy.Heaviside,
        "Heaviside": sympy.Heaviside,
        "dirac": sympy.DiracDelta,
        "Dirac": sympy.DiracDelta,
        "piecewise": sympy.Piecewise,
        "Piecewise": sympy.Piecewise,
        "sign": sympy.sign,
        "sawtooth": _SAWTOOTH_FUNCTION,
        "rand": _RAND_FUNCTION,
        "randn": _RANDN_FUNCTION,
        "Abs": sympy.Abs,
        "Min": sympy.Min,
        "Max": sympy.Max,
    }
)

_LEAF_NATIVE_SOURCE_KINDS = frozenset(
    {"constant", "time", "step", "impulse", "pulse", "sine", "ramp", "square", "sawtooth", "triangle"}
)
_NATIVE_SOURCE_KINDS = _LEAF_NATIVE_SOURCE_KINDS | frozenset(
    {
        "sum",
        "product",
        "power",
        "exp",
        "delay",
        "trig_function",
        "binary_trig_function",
        "reciprocal_trig_function",
        "math_function",
        "minmax",
        "saturation",
        "dead_zone",
        "abs",
        "sign",
        "piecewise",
        "relay",
        "random_number",
        "white_noise",
    }
)

_DIRECT_TRIG_EVALUATORS: dict[str, callable] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "asinh": math.asinh,
    "acosh": math.acosh,
    "atanh": math.atanh,
}
_RECIPROCAL_TRIG_EVALUATORS: dict[str, callable] = {
    "sec": math.cos,
    "csc": math.sin,
    "cot": math.tan,
    "sech": math.cosh,
    "csch": math.sinh,
    "coth": math.tanh,
}
_DIRECT_MATH_EVALUATORS: dict[str, callable] = {
    "exp": math.exp,
    "log": math.log,
    "sqrt": math.sqrt,
}


def build_input_function(
    *,
    base_input_function: InputFunction | None = None,
    constant_values: Mapping[str, object] | None = None,
    input_specs: Mapping[str, object] | None = None,
    t_span: tuple[float, float] = (0.0, 10.0),
) -> InputFunction:
    """Overlay constant values and waveform specs on top of an existing input function."""
    base = base_input_function or constant_inputs({})
    normalized_constants = _normalize_constant_values(constant_values)
    normalized_specs = normalize_input_specs(input_specs=input_specs, t_span=t_span)
    compiled_specs = {
        name: _compile_input_spec(name, spec, t_span=t_span)
        for name, spec in normalized_specs.items()
    }
    if not normalized_constants and not compiled_specs:
        return base

    def _input(time_value: float) -> dict[str, float]:
        values = dict(base(float(time_value)))
        values.update(normalized_constants)
        for name, evaluator in compiled_specs.items():
            values[name] = evaluator(float(time_value))
        return values

    return _input


def normalize_input_specs(
    *,
    input_specs: Mapping[str, object] | None = None,
    t_span: tuple[float, float] = (0.0, 10.0),
) -> dict[str, dict[str, object]]:
    """Return canonical runtime input specs with native-block-friendly kinds when possible."""
    return {
        str(name): _canonicalize_input_spec(str(name), raw_spec, t_span=t_span)
        for name, raw_spec in dict(input_specs or {}).items()
    }


def native_source_specs(
    *,
    input_specs: Mapping[str, object] | None = None,
    t_span: tuple[float, float] = (0.0, 10.0),
) -> dict[str, dict[str, object]]:
    """Return canonical input specs that can map directly to native Simulink source blocks."""
    normalized = normalize_input_specs(input_specs=input_specs, t_span=t_span)
    return {
        name: spec
        for name, spec in normalized.items()
        if _is_native_source_spec(spec)
    }


def _normalize_constant_values(raw_values: Mapping[str, object] | None) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for name, raw_value in dict(raw_values or {}).items():
        try:
            normalized[str(name)] = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise DeterministicCompileError(
                f"Runtime override input value for {name!r} must be numeric."
            ) from exc
    return normalized


def _compile_input_spec(
    input_name: str,
    raw_spec: object,
    *,
    t_span: tuple[float, float],
):
    spec = _canonicalize_input_spec(input_name, raw_spec, t_span=t_span)
    return _compile_canonical_input_spec(input_name, spec, t_span=t_span)


def _compile_canonical_input_spec(
    input_name: str,
    spec: Mapping[str, object],
    *,
    t_span: tuple[float, float],
):
    kind = spec["kind"]
    if kind == "constant":
        value = _numeric_field(spec, input_name, names=("value", "amplitude"), default=1.0)
        return lambda _time: value
    if kind == "time":
        return lambda time_value: float(time_value)
    if kind == "step":
        amplitude = _numeric_field(spec, input_name, names=("amplitude", "value"), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay"), default=0.0)
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        return lambda time_value: bias + (amplitude if time_value >= start_time else 0.0)
    if kind == "impulse":
        amplitude = _numeric_field(spec, input_name, names=("amplitude", "area", "value"), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay"), default=float(t_span[0]))
        default_width = max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-6)
        width = _numeric_field(spec, input_name, names=("width", "duration"), default=default_width)
        if width <= 0.0:
            raise DeterministicCompileError(
                f"Runtime override impulse width for input {input_name!r} must be positive."
            )
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        height = amplitude / width
        return lambda time_value: bias + (height if start_time <= time_value < start_time + width else 0.0)
    if kind == "pulse":
        amplitude = _numeric_field(spec, input_name, names=("amplitude", "value"), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay", "phase_delay"), default=0.0)
        default_width = max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-6)
        width = _numeric_field(spec, input_name, names=("width", "duration"), default=default_width)
        if width <= 0.0:
            raise DeterministicCompileError(
                f"Runtime override pulse width for input {input_name!r} must be positive."
            )
        period = _numeric_field(
            spec,
            input_name,
            names=("period",),
            default=_default_pulse_period(start_time=start_time, width=width, t_span=t_span),
        )
        if period <= 0.0:
            raise DeterministicCompileError(
                f"Runtime override pulse period for input {input_name!r} must be positive."
            )
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        return lambda time_value: bias + (
            amplitude if _pulse_is_active(time_value, start_time=start_time, width=width, period=period) else 0.0
        )
    if kind == "sine":
        amplitude = _numeric_field(spec, input_name, names=("amplitude",), default=1.0)
        frequency = _numeric_field(spec, input_name, names=("frequency", "omega"), default=1.0)
        phase = _numeric_field(spec, input_name, names=("phase",), default=0.0)
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        return lambda time_value: bias + amplitude * math.sin(frequency * time_value + phase)
    if kind == "square":
        amplitude = _numeric_field(spec, input_name, names=("amplitude",), default=1.0)
        frequency = _numeric_field(spec, input_name, names=("frequency", "omega"), default=1.0)
        phase = _numeric_field(spec, input_name, names=("phase",), default=0.0)
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        return lambda time_value: bias + amplitude * (1.0 if math.sin(frequency * time_value + phase) >= 0.0 else -1.0)
    if kind in {"sawtooth", "triangle"}:
        amplitude = _numeric_field(spec, input_name, names=("amplitude",), default=1.0)
        frequency = _numeric_field(spec, input_name, names=("frequency", "omega"), default=1.0)
        phase = _numeric_field(spec, input_name, names=("phase",), default=0.0)
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        width = _numeric_field(spec, input_name, names=("width",), default=0.5 if kind == "triangle" else 1.0)
        return lambda time_value: bias + amplitude * _sawtooth_wave(frequency * time_value + phase, width=width)
    if kind == "ramp":
        slope = _numeric_field(spec, input_name, names=("slope",), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay"), default=0.0)
        initial_output = _numeric_field(spec, input_name, names=("initial_output", "bias", "offset"), default=0.0)
        return lambda time_value: (
            initial_output if time_value < start_time else initial_output + slope * (time_value - start_time)
        )
    if kind == "sum":
        terms = spec.get("terms")
        if not isinstance(terms, (list, tuple)) or not terms:
            raise DeterministicCompileError(
                f"Runtime input sum spec for {input_name!r} must include a non-empty 'terms' list."
            )
        evaluators = [
            _compile_canonical_input_spec(input_name, _canonicalize_input_spec(input_name, term, t_span=t_span), t_span=t_span)
            for term in terms
        ]
        return lambda time_value: sum(evaluator(time_value) for evaluator in evaluators)
    if kind == "product":
        terms = spec.get("terms")
        if not isinstance(terms, (list, tuple)) or not terms:
            raise DeterministicCompileError(
                f"Runtime input product spec for {input_name!r} must include a non-empty 'terms' list."
            )
        evaluators = [
            _compile_canonical_input_spec(input_name, _canonicalize_input_spec(input_name, term, t_span=t_span), t_span=t_span)
            for term in terms
        ]
        return lambda time_value: math.prod(evaluator(time_value) for evaluator in evaluators)
    if kind == "power":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        exponent = _numeric_field(spec, input_name, names=("exponent",), default=1.0)
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: evaluator(time_value) ** exponent
    if kind == "exp":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: math.exp(evaluator(time_value))
    if kind == "trig_function":
        operator = str(spec.get("operator", "")).strip().lower()
        if operator not in _DIRECT_TRIG_EVALUATORS:
            raise DeterministicCompileError(
                f"Runtime input trig_function spec for {input_name!r} uses unsupported operator {operator!r}."
            )
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        trig_evaluator = _DIRECT_TRIG_EVALUATORS[operator]
        return lambda time_value: trig_evaluator(evaluator(time_value))
    if kind == "binary_trig_function":
        operator = str(spec.get("operator", "")).strip().lower()
        if operator != "atan2":
            raise DeterministicCompileError(
                f"Runtime input binary_trig_function spec for {input_name!r} uses unsupported operator {operator!r}."
            )
        lhs_spec = _extract_nested_input_spec(spec, input_name, field_names=("lhs", "y", "input1"))
        rhs_spec = _extract_nested_input_spec(spec, input_name, field_names=("rhs", "x", "input2"))
        lhs_evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, lhs_spec, t_span=t_span),
            t_span=t_span,
        )
        rhs_evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, rhs_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: math.atan2(lhs_evaluator(time_value), rhs_evaluator(time_value))
    if kind == "reciprocal_trig_function":
        operator = str(spec.get("operator", "")).strip().lower()
        if operator not in _RECIPROCAL_TRIG_EVALUATORS:
            raise DeterministicCompileError(
                f"Runtime input reciprocal_trig_function spec for {input_name!r} uses unsupported operator {operator!r}."
            )
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        base_evaluator = _RECIPROCAL_TRIG_EVALUATORS[operator]
        def _reciprocal_trig(time_value: float) -> float:
            base_value = float(base_evaluator(evaluator(time_value)))
            if abs(base_value) <= 1e-12:
                raise DeterministicCompileError(
                    f"Runtime input reciprocal trig function {operator!r} for {input_name!r} encountered a zero denominator."
                )
            return 1.0 / base_value
        return _reciprocal_trig
    if kind == "math_function":
        operator = str(spec.get("operator", "")).strip().lower()
        if operator not in _DIRECT_MATH_EVALUATORS:
            raise DeterministicCompileError(
                f"Runtime input math_function spec for {input_name!r} uses unsupported operator {operator!r}."
            )
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        math_evaluator = _DIRECT_MATH_EVALUATORS[operator]
        return lambda time_value: math_evaluator(evaluator(time_value))
    if kind == "minmax":
        operator = str(spec.get("operator", "")).strip().lower()
        if operator not in DIRECT_SIMULINK_MINMAX_FUNCTIONS:
            raise DeterministicCompileError(
                f"Runtime input minmax spec for {input_name!r} uses unsupported operator {operator!r}."
            )
        terms = spec.get("terms")
        if not isinstance(terms, (list, tuple)) or not terms:
            raise DeterministicCompileError(
                f"Runtime input minmax spec for {input_name!r} must include a non-empty 'terms' list."
            )
        evaluators = [
            _compile_canonical_input_spec(input_name, _canonicalize_input_spec(input_name, term, t_span=t_span), t_span=t_span)
            for term in terms
        ]
        if operator == "min":
            return lambda time_value: min(evaluator(time_value) for evaluator in evaluators)
        return lambda time_value: max(evaluator(time_value) for evaluator in evaluators)
    if kind == "delay":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        delay_time = _numeric_field(spec, input_name, names=("delay_time", "delay"), default=0.0)
        initial_output = _numeric_field(spec, input_name, names=("initial_output", "bias", "offset"), default=0.0)
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: initial_output if time_value < delay_time else evaluator(time_value - delay_time)
    if kind == "saturation":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        lower_limit = _numeric_field(spec, input_name, names=("lower_limit", "lower", "min"), default=-1.0)
        upper_limit = _numeric_field(spec, input_name, names=("upper_limit", "upper", "max"), default=1.0)
        if lower_limit > upper_limit:
            raise DeterministicCompileError(
                f"Runtime saturation spec for input {input_name!r} must satisfy lower_limit <= upper_limit."
        )
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: min(max(evaluator(time_value), lower_limit), upper_limit)
    if kind == "dead_zone":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        lower_limit = _numeric_field(spec, input_name, names=("lower_limit", "lower"), default=-1.0)
        upper_limit = _numeric_field(spec, input_name, names=("upper_limit", "upper"), default=1.0)
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: _dead_zone_value(evaluator(time_value), lower_limit=lower_limit, upper_limit=upper_limit)
    if kind == "abs":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: abs(evaluator(time_value))
    if kind == "sign":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        return lambda time_value: _sign_value(evaluator(time_value))
    if kind == "relay":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            t_span=t_span,
        )
        on_switch = _numeric_field(spec, input_name, names=("on_switch_value", "on_threshold"), default=0.0)
        off_switch = _numeric_field(spec, input_name, names=("off_switch_value", "off_threshold"), default=0.0)
        on_output = _numeric_field(spec, input_name, names=("on_output_value",), default=1.0)
        off_output = _numeric_field(spec, input_name, names=("off_output_value",), default=-1.0)
        state = {"value": off_output}
        def _relay(time_value: float) -> float:
            sample = evaluator(time_value)
            if sample >= on_switch:
                state["value"] = on_output
            elif sample <= off_switch:
                state["value"] = off_output
            return float(state["value"])
        return _relay
    if kind == "piecewise":
        branches = spec.get("branches")
        if not isinstance(branches, (list, tuple)) or not branches:
            raise DeterministicCompileError(
                f"Runtime input piecewise spec for {input_name!r} must include a non-empty 'branches' list."
            )
        compiled_branches = []
        for branch in branches:
            if not isinstance(branch, Mapping):
                raise DeterministicCompileError(
                    f"Runtime input piecewise spec for {input_name!r} must use object branches."
                )
            compiled_branches.append(
                (
                    _compile_condition_spec(branch.get("condition", True), input_name, t_span=t_span),
                    _compile_canonical_input_spec(
                        input_name,
                        _canonicalize_input_spec(input_name, branch.get("value"), t_span=t_span),
                        t_span=t_span,
                    ),
                )
            )
        otherwise = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, spec.get("otherwise", {"kind": "constant", "value": 0.0}), t_span=t_span),
            t_span=t_span,
        )
        def _piecewise(time_value: float) -> float:
            for condition, value in compiled_branches:
                if condition(time_value):
                    return float(value(time_value))
            return float(otherwise(time_value))
        return _piecewise
    if kind in {"random_number", "white_noise"}:
        seed = int(_numeric_field(spec, input_name, names=("seed",), default=0.0))
        sample_time = _numeric_field(spec, input_name, names=("sample_time", "ts"), default=max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-3))
        return _deterministic_noise_function(
            mean=_numeric_field(spec, input_name, names=("mean",), default=0.0),
            variance=_numeric_field(spec, input_name, names=("variance", "covariance", "cov"), default=1.0),
            seed=seed,
            sample_time=sample_time,
            gaussian=(kind == "white_noise"),
            minimum=_numeric_field(spec, input_name, names=("minimum", "lower"), default=0.0),
            maximum=_numeric_field(spec, input_name, names=("maximum", "upper"), default=1.0),
        )
    if kind == "expression":
        expression, time_variable, time_symbol = _parse_expression_spec(input_name, spec)
        def _heaviside(argument: float, h0: float = 1.0) -> float:
            if argument > 0.0:
                return 1.0
            if argument < 0.0:
                return 0.0
            return float(h0)

        compiled = sympy.lambdify(
            [time_symbol],
            expression,
            modules=[{"Heaviside": _heaviside, "heaviside": _heaviside}, "math"],
        )
        return lambda time_value: float(compiled(float(time_value)))
    raise DeterministicCompileError(
        f"Unsupported runtime input spec kind {kind!r} for input {input_name!r}."
    )


def _canonicalize_input_spec(
    input_name: str,
    raw_spec: object,
    *,
    t_span: tuple[float, float],
) -> dict[str, object]:
    spec = _normalize_input_spec(input_name, raw_spec)
    kind = str(spec["kind"])
    if kind == "constant":
        return {"kind": "constant", "value": _numeric_field(spec, input_name, names=("value", "amplitude"), default=1.0)}
    if kind == "time":
        return {"kind": "time"}
    if kind == "step":
        amplitude = _numeric_field(spec, input_name, names=("amplitude", "value"), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay"), default=0.0)
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        return {
            "kind": "step",
            "amplitude": amplitude,
            "start_time": start_time,
            "bias": bias,
        }
    if kind == "impulse":
        amplitude = _numeric_field(spec, input_name, names=("amplitude", "area", "value"), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay"), default=float(t_span[0]))
        default_width = max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-6)
        width = _numeric_field(spec, input_name, names=("width", "duration"), default=default_width)
        if width <= 0.0:
            raise DeterministicCompileError(
                f"Runtime override impulse width for input {input_name!r} must be positive."
            )
        bias = _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0)
        return {
            "kind": "impulse",
            "amplitude": amplitude,
            "start_time": start_time,
            "width": width,
            "period": _numeric_field(
                spec,
                input_name,
                names=("period",),
                default=_default_pulse_period(start_time=start_time, width=width, t_span=t_span),
            ),
            "bias": bias,
        }
    if kind == "pulse":
        amplitude = _numeric_field(spec, input_name, names=("amplitude", "value"), default=1.0)
        start_time = _numeric_field(spec, input_name, names=("start_time", "start", "delay", "phase_delay"), default=0.0)
        default_width = max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-6)
        width = _numeric_field(spec, input_name, names=("width", "duration"), default=default_width)
        if width <= 0.0:
            raise DeterministicCompileError(
                f"Runtime override pulse width for input {input_name!r} must be positive."
            )
        period = _numeric_field(
            spec,
            input_name,
            names=("period",),
            default=_default_pulse_period(start_time=start_time, width=width, t_span=t_span),
        )
        if period <= 0.0:
            raise DeterministicCompileError(
                f"Runtime override pulse period for input {input_name!r} must be positive."
            )
        return {
            "kind": "pulse",
            "amplitude": amplitude,
            "start_time": start_time,
            "width": width,
            "period": period,
            "bias": _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0),
        }
    if kind == "sine":
        return {
            "kind": "sine",
            "amplitude": _numeric_field(spec, input_name, names=("amplitude",), default=1.0),
            "frequency": _numeric_field(spec, input_name, names=("frequency", "omega"), default=1.0),
            "phase": _numeric_field(spec, input_name, names=("phase",), default=0.0),
            "bias": _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0),
        }
    if kind == "square":
        return {
            "kind": "square",
            "amplitude": _numeric_field(spec, input_name, names=("amplitude",), default=1.0),
            "frequency": _numeric_field(spec, input_name, names=("frequency", "omega"), default=1.0),
            "phase": _numeric_field(spec, input_name, names=("phase",), default=0.0),
            "bias": _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0),
        }
    if kind in {"sawtooth", "triangle"}:
        width_default = 0.5 if kind == "triangle" else 1.0
        return {
            "kind": kind,
            "amplitude": _numeric_field(spec, input_name, names=("amplitude",), default=1.0),
            "frequency": _numeric_field(spec, input_name, names=("frequency", "omega"), default=1.0),
            "phase": _numeric_field(spec, input_name, names=("phase",), default=0.0),
            "bias": _numeric_field(spec, input_name, names=("bias", "offset"), default=0.0),
            "width": _numeric_field(spec, input_name, names=("width",), default=width_default),
        }
    if kind == "ramp":
        return {
            "kind": "ramp",
            "slope": _numeric_field(spec, input_name, names=("slope",), default=1.0),
            "start_time": _numeric_field(spec, input_name, names=("start_time", "start", "delay"), default=0.0),
            "initial_output": _numeric_field(spec, input_name, names=("initial_output", "bias", "offset"), default=0.0),
        }
    if kind == "sum":
        terms = spec.get("terms")
        if not isinstance(terms, (list, tuple)) or not terms:
            raise DeterministicCompileError(
                f"Runtime input sum spec for {input_name!r} must include a non-empty 'terms' list."
            )
        return {
            "kind": "sum",
            "terms": [_canonicalize_input_spec(input_name, term, t_span=t_span) for term in terms],
        }
    if kind == "product":
        terms = spec.get("terms")
        if not isinstance(terms, (list, tuple)) or not terms:
            raise DeterministicCompileError(
                f"Runtime input product spec for {input_name!r} must include a non-empty 'terms' list."
            )
        return {
            "kind": "product",
            "terms": [_canonicalize_input_spec(input_name, term, t_span=t_span) for term in terms],
        }
    if kind == "power":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        return {
            "kind": "power",
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            "exponent": _numeric_field(spec, input_name, names=("exponent",), default=1.0),
        }
    if kind == "exp":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        return {
            "kind": "exp",
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
        }
    if kind == "delay":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        return {
            "kind": "delay",
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            "delay_time": _numeric_field(spec, input_name, names=("delay_time", "delay"), default=0.0),
            "initial_output": _numeric_field(spec, input_name, names=("initial_output", "bias", "offset"), default=0.0),
        }
    if kind == "saturation":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        lower_limit = _numeric_field(spec, input_name, names=("lower_limit", "lower", "min"), default=-1.0)
        upper_limit = _numeric_field(spec, input_name, names=("upper_limit", "upper", "max"), default=1.0)
        if lower_limit > upper_limit:
            raise DeterministicCompileError(
                f"Runtime saturation spec for input {input_name!r} must satisfy lower_limit <= upper_limit."
            )
        return {
            "kind": "saturation",
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            "lower_limit": lower_limit,
            "upper_limit": upper_limit,
        }
    if kind == "dead_zone":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        lower_limit = _numeric_field(spec, input_name, names=("lower_limit", "lower"), default=-1.0)
        upper_limit = _numeric_field(spec, input_name, names=("upper_limit", "upper"), default=1.0)
        if lower_limit > upper_limit:
            raise DeterministicCompileError(
                f"Runtime dead-zone spec for input {input_name!r} must satisfy lower_limit <= upper_limit."
            )
        return {
            "kind": "dead_zone",
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            "lower_limit": lower_limit,
            "upper_limit": upper_limit,
        }
    if kind in {"abs", "sign"}:
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        return {
            "kind": kind,
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
        }
    if kind == "relay":
        inner_spec = _extract_nested_input_spec(spec, input_name, field_names=("input", "source", "inner"))
        return {
            "kind": "relay",
            "input": _canonicalize_input_spec(input_name, inner_spec, t_span=t_span),
            "on_switch_value": _numeric_field(spec, input_name, names=("on_switch_value", "on_threshold"), default=0.0),
            "off_switch_value": _numeric_field(spec, input_name, names=("off_switch_value", "off_threshold"), default=0.0),
            "on_output_value": _numeric_field(spec, input_name, names=("on_output_value",), default=1.0),
            "off_output_value": _numeric_field(spec, input_name, names=("off_output_value",), default=-1.0),
        }
    if kind == "piecewise":
        branches = spec.get("branches")
        if not isinstance(branches, (list, tuple)) or not branches:
            raise DeterministicCompileError(
                f"Runtime input piecewise spec for {input_name!r} must include a non-empty 'branches' list."
            )
        time_variable = str(spec.get("time_variable", "t"))
        time_symbol = sympy.Symbol(time_variable)
        normalized_branches: list[dict[str, object]] = []
        for branch in branches:
            if not isinstance(branch, Mapping):
                raise DeterministicCompileError(
                    f"Runtime input piecewise spec for {input_name!r} must use object branches."
                )
            normalized_branches.append(
                {
                    "condition": _canonicalize_condition_spec(branch.get("condition", True), input_name, time_symbol, t_span=t_span),
                    "value": _canonicalize_input_spec(input_name, branch.get("value"), t_span=t_span),
                }
            )
        otherwise_spec = _canonicalize_input_spec(
            input_name,
            spec.get("otherwise", {"kind": "constant", "value": 0.0}),
            t_span=t_span,
        )
        return {
            "kind": "piecewise",
            "branches": normalized_branches,
            "otherwise": otherwise_spec,
        }
    if kind in {"random_number", "white_noise"}:
        normalized = {"kind": kind}
        if kind == "random_number":
            normalized["minimum"] = _numeric_field(spec, input_name, names=("minimum", "lower"), default=0.0)
            normalized["maximum"] = _numeric_field(spec, input_name, names=("maximum", "upper"), default=1.0)
            if float(normalized["minimum"]) > float(normalized["maximum"]):
                raise DeterministicCompileError(
                    f"Runtime random-number spec for input {input_name!r} must satisfy minimum <= maximum."
                )
        else:
            normalized["mean"] = _numeric_field(spec, input_name, names=("mean",), default=0.0)
            normalized["variance"] = _numeric_field(spec, input_name, names=("variance", "covariance", "cov"), default=1.0)
        normalized["seed"] = int(_numeric_field(spec, input_name, names=("seed",), default=0.0))
        normalized["sample_time"] = _numeric_field(
            spec,
            input_name,
            names=("sample_time", "ts"),
            default=max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-3),
        )
        return normalized
    if kind != "expression":
        return spec

    expression, time_variable, time_symbol = _parse_expression_spec(input_name, spec)
    saturation_spec = _match_saturation_expression(expression, time_symbol, t_span=t_span)
    if saturation_spec is not None:
        return saturation_spec
    dead_zone_spec = _match_dead_zone_expression(expression, time_symbol, t_span=t_span)
    if dead_zone_spec is not None:
        return dead_zone_spec
    ramp_spec = _match_ramp_expression(expression, time_symbol)
    if ramp_spec is not None:
        return ramp_spec
    sine_spec = _match_sine_expression(expression, time_symbol)
    if sine_spec is not None:
        return sine_spec
    square_spec = _match_square_expression(expression, time_symbol)
    if square_spec is not None:
        return square_spec
    sawtooth_spec = _match_sawtooth_expression(expression, time_symbol)
    if sawtooth_spec is not None:
        return sawtooth_spec
    step_spec = _match_step_expression(expression, time_symbol)
    if step_spec is not None:
        pulse_spec = _match_pulse_from_step_spec(step_spec, t_span=t_span)
        if pulse_spec is not None:
            return pulse_spec
        return step_spec
    impulse_spec = _match_impulse_expression(expression, time_symbol, t_span=t_span)
    if impulse_spec is not None:
        return impulse_spec
    piecewise_spec = _match_piecewise_expression(expression, time_symbol, t_span=t_span)
    if piecewise_spec is not None:
        return piecewise_spec
    random_spec = _match_random_expression(expression, t_span=t_span)
    if random_spec is not None:
        return random_spec
    if not expression.free_symbols:
        return {"kind": "constant", "value": float(expression)}
    native_spec = _canonicalize_native_expression_tree(expression, time_symbol, t_span=t_span)
    if native_spec is not None:
        return native_spec
    return {
        "kind": "expression",
        "expression": str(spec["expression"]).strip(),
        "time_variable": time_variable,
    }


def _normalize_input_spec(input_name: str, raw_spec: object) -> dict[str, object]:
    if isinstance(raw_spec, str):
        kind = raw_spec.strip().lower()
        if not kind:
            raise DeterministicCompileError(
                f"Runtime input spec for {input_name!r} must not be empty."
            )
        return {"kind": kind}
    if not isinstance(raw_spec, Mapping):
        raise DeterministicCompileError(
            f"Runtime input spec for {input_name!r} must be a string keyword or an object."
        )
    spec = dict(raw_spec)
    kind = spec.get("kind", spec.get("type"))
    if not isinstance(kind, str) or not kind.strip():
        raise DeterministicCompileError(
            f"Runtime input spec for {input_name!r} must include a non-empty string 'kind'."
        )
    spec["kind"] = kind.strip().lower()
    return spec


def _parse_expression_spec(
    input_name: str,
    spec: Mapping[str, object],
) -> tuple[sympy.Expr, str, sympy.Symbol]:
    expression_text = spec.get("expression")
    if not isinstance(expression_text, str) or not expression_text.strip():
        raise DeterministicCompileError(
            f"Runtime input expression for {input_name!r} must include a non-empty 'expression' string."
        )
    time_variable = spec.get("time_variable", "t")
    if not isinstance(time_variable, str) or not time_variable.strip():
        raise DeterministicCompileError(
            f"Runtime input expression for {input_name!r} must use a non-empty string time variable."
        )
    normalized_time_variable = time_variable.strip()
    time_symbol = sympy.Symbol(normalized_time_variable)
    normalized_expression_text = _normalize_matlab_expression_text(expression_text.strip())
    try:
        expression = parse_expr(
            normalized_expression_text,
            local_dict=dict(_INPUT_SPEC_LOCALS),
            transformations=_PARSE_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise DeterministicCompileError(
            f"Runtime input expression for {input_name!r} could not be parsed: {expression_text!r}."
        ) from exc
    extra_symbols = {str(symbol) for symbol in expression.free_symbols if symbol != time_symbol}
    if extra_symbols:
        raise DeterministicCompileError(
            f"Runtime input expression for {input_name!r} must depend only on {normalized_time_variable!r}; "
            f"found extra symbols: {sorted(extra_symbols)}."
        )
    return expression, normalized_time_variable, time_symbol


def _normalize_matlab_expression_text(expression_text: str) -> str:
    normalized = expression_text
    while True:
        rewritten, changed = _rewrite_matlab_array_extrema(normalized)
        if not changed:
            return rewritten
        normalized = rewritten


def _rewrite_matlab_array_extrema(expression_text: str) -> tuple[str, bool]:
    index = 0
    pieces: list[str] = []
    changed = False
    while index < len(expression_text):
        if expression_text.startswith("min([", index) or expression_text.startswith("max([", index):
            replacement, next_index = _rewrite_single_matlab_array_extrema(expression_text, index)
            if replacement is not None:
                pieces.append(replacement)
                index = next_index
                changed = True
                continue
        pieces.append(expression_text[index])
        index += 1
    return "".join(pieces), changed


def _rewrite_single_matlab_array_extrema(expression_text: str, start_index: int) -> tuple[str | None, int]:
    function_name = "min" if expression_text.startswith("min([", start_index) else "max"
    array_start = start_index + len(function_name) + 1
    array_end = _find_matching_delimiter(expression_text, array_start, "[", "]")
    if array_end is None:
        return None, start_index
    call_end = _find_matching_delimiter(expression_text, start_index + len(function_name), "(", ")")
    if call_end is None:
        return None, start_index
    array_items = _split_top_level_arguments(expression_text[array_start + 1:array_end], delimiter=",")
    normalized_items = [_normalize_matlab_expression_text(item.strip()) for item in array_items if item.strip()]
    if not normalized_items:
        return None, start_index
    return f"{function_name}(" + ", ".join(normalized_items) + ")", call_end + 1


def _find_matching_delimiter(
    text: str,
    start_index: int,
    open_char: str,
    close_char: str,
) -> int | None:
    depth = 0
    quote_char: str | None = None
    index = start_index
    while index < len(text):
        character = text[index]
        if quote_char is not None:
            if character == quote_char:
                quote_char = None
            index += 1
            continue
        if character in {"'", '"'}:
            quote_char = character
            index += 1
            continue
        if character == open_char:
            depth += 1
        elif character == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _split_top_level_arguments(argument_text: str, *, delimiter: str) -> list[str]:
    arguments: list[str] = []
    current: list[str] = []
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    quote_char: str | None = None
    for character in argument_text:
        if quote_char is not None:
            current.append(character)
            if character == quote_char:
                quote_char = None
            continue
        if character in {"'", '"'}:
            quote_char = character
            current.append(character)
            continue
        if character == "(":
            paren_depth += 1
        elif character == ")":
            paren_depth -= 1
        elif character == "[":
            bracket_depth += 1
        elif character == "]":
            bracket_depth -= 1
        elif character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth -= 1
        elif (
            character == delimiter
            and paren_depth == 0
            and bracket_depth == 0
            and brace_depth == 0
        ):
            arguments.append("".join(current))
            current = []
            continue
        current.append(character)
    arguments.append("".join(current))
    return arguments


def _canonicalize_native_expression_tree(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    simplified = sympy.simplify(expression)
    if not simplified.free_symbols:
        numeric_value = _extract_numeric_expr(simplified)
        if numeric_value is None:
            return None
        return {"kind": "constant", "value": numeric_value}
    if simplified == time_symbol:
        return {"kind": "time"}
    for matcher in (
        lambda expr: _match_saturation_expression(expr, time_symbol, t_span=t_span),
        lambda expr: _match_dead_zone_expression(expr, time_symbol, t_span=t_span),
        lambda expr: _match_ramp_expression(expr, time_symbol),
        lambda expr: _match_sine_expression(expr, time_symbol),
        lambda expr: _match_square_expression(expr, time_symbol),
        lambda expr: _match_sawtooth_expression(expr, time_symbol),
        lambda expr: _match_step_expression(expr, time_symbol),
        lambda expr: _match_impulse_expression(expr, time_symbol, t_span=t_span),
        lambda expr: _match_piecewise_expression(expr, time_symbol, t_span=t_span),
        lambda expr: _match_random_expression(expr, t_span=t_span),
    ):
        matched = matcher(simplified)
        if matched is not None:
            pulse_spec = _match_pulse_from_step_spec(matched, t_span=t_span)
            if pulse_spec is not None:
                return pulse_spec
            return matched
    if simplified.func == sympy.Add:
        terms = [
            _canonicalize_native_expression_tree(term, time_symbol, t_span=t_span)
            for term in sympy.Add.make_args(simplified)
        ]
        if any(term is None for term in terms):
            return None
        return _flatten_variadic_spec("sum", terms)  # type: ignore[arg-type]
    if simplified.func == sympy.Mul:
        terms = [
            _canonicalize_native_expression_tree(term, time_symbol, t_span=t_span)
            for term in sympy.Mul.make_args(simplified)
        ]
        if any(term is None for term in terms):
            return None
        return _flatten_variadic_spec("product", terms)  # type: ignore[arg-type]
    if simplified.func == sympy.Pow and len(simplified.args) == 2:
        base_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        exponent = _extract_numeric_expr(simplified.args[1])
        if base_spec is None or exponent is None:
            return None
        return {"kind": "power", "input": base_spec, "exponent": exponent}
    if simplified.func == sympy.exp and len(simplified.args) == 1:
        inner_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        if inner_spec is None:
            return None
        return {"kind": "exp", "input": inner_spec}
    function_name = _sympy_function_name(simplified.func)
    if function_name in DIRECT_SIMULINK_TRIG_FUNCTIONS and len(simplified.args) == 1:
        inner_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        if inner_spec is None:
            return None
        return {"kind": "trig_function", "operator": function_name, "input": inner_spec}
    if function_name in DIRECT_SIMULINK_BINARY_TRIG_FUNCTIONS and len(simplified.args) == 2:
        lhs_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        rhs_spec = _canonicalize_native_expression_tree(simplified.args[1], time_symbol, t_span=t_span)
        if lhs_spec is None or rhs_spec is None:
            return None
        return {"kind": "binary_trig_function", "operator": function_name, "lhs": lhs_spec, "rhs": rhs_spec}
    if function_name in RECIPROCAL_FUNCTION_BASES and len(simplified.args) == 1:
        inner_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        if inner_spec is None:
            return None
        return {"kind": "reciprocal_trig_function", "operator": function_name, "input": inner_spec}
    if function_name in DIRECT_SIMULINK_MATH_FUNCTIONS and len(simplified.args) == 1:
        inner_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        if inner_spec is None:
            return None
        return {"kind": "math_function", "operator": function_name, "input": inner_spec}
    if function_name in DIRECT_SIMULINK_MINMAX_FUNCTIONS and simplified.args:
        terms = [
            _canonicalize_native_expression_tree(term, time_symbol, t_span=t_span)
            for term in simplified.args
        ]
        if any(term is None for term in terms):
            return None
        return {"kind": "minmax", "operator": function_name, "terms": terms}  # type: ignore[arg-type]
    if simplified.func == sympy.Abs and len(simplified.args) == 1:
        inner_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        if inner_spec is None:
            return None
        return {"kind": "abs", "input": inner_spec}
    if simplified.func == sympy.sign and len(simplified.args) == 1:
        inner_spec = _canonicalize_native_expression_tree(simplified.args[0], time_symbol, t_span=t_span)
        if inner_spec is None:
            return None
        return {"kind": "sign", "input": inner_spec}
    if simplified.func == sympy.Piecewise:
        return _match_piecewise_expression(simplified, time_symbol, t_span=t_span)
    if simplified.func == _RAND_FUNCTION:
        return _match_random_expression(simplified, t_span=t_span)
    if simplified.func == _RANDN_FUNCTION:
        return _match_random_expression(simplified, t_span=t_span)
    return None


def _flatten_variadic_spec(kind: str, terms: list[dict[str, object]]) -> dict[str, object]:
    flattened: list[dict[str, object]] = []
    for term in terms:
        if str(term.get("kind", "")) == kind:
            nested_terms = term.get("terms")
            if isinstance(nested_terms, list):
                flattened.extend(nested_terms)
                continue
        flattened.append(term)
    if len(flattened) == 1:
        return flattened[0]
    return {"kind": kind, "terms": flattened}


def _sympy_function_name(function: object) -> str:
    name = getattr(function, "__name__", "")
    if isinstance(name, str) and name:
        return name.lower()
    return str(function).strip().lower()


def _match_square_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
) -> dict[str, object] | None:
    expanded = sympy.expand(expression)
    square_term: tuple[float, float, float] | None = None
    bias = 0.0
    for term in sympy.Add.make_args(expanded):
        coefficient, remainder = term.as_coeff_Mul()
        if remainder.func == sympy.sign and len(remainder.args) == 1:
            argument = remainder.args[0]
            if argument.func not in {sympy.sin, sympy.cos} or len(argument.args) != 1:
                return None
            if square_term is not None:
                return None
            frequency, phase = _extract_linear_phase(argument.args[0], time_symbol)
            if frequency is None:
                return None
            if argument.func == sympy.cos:
                phase += math.pi / 2.0
            square_term = (float(coefficient), float(frequency), float(phase))
            continue
        if term.free_symbols:
            return None
        numeric_term = _extract_numeric_expr(term)
        if numeric_term is None:
            return None
        bias += numeric_term
    if square_term is None:
        return None
    return {
        "kind": "square",
        "amplitude": square_term[0],
        "frequency": square_term[1],
        "phase": square_term[2],
        "bias": float(bias),
    }


def _match_sawtooth_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
) -> dict[str, object] | None:
    expanded = sympy.expand(expression)
    waveform_term: tuple[str, float, float, float] | None = None
    bias = 0.0
    for term in sympy.Add.make_args(expanded):
        coefficient, remainder = term.as_coeff_Mul()
        if remainder.func == _SAWTOOTH_FUNCTION and remainder.args:
            if waveform_term is not None:
                return None
            frequency, phase = _extract_linear_phase(remainder.args[0], time_symbol)
            if frequency is None:
                return None
            width = 1.0
            if len(remainder.args) >= 2:
                width_value = _extract_numeric_expr(remainder.args[1])
                if width_value is None:
                    return None
                width = float(width_value)
            kind = "triangle" if math.isclose(width, 0.5, rel_tol=0.0, abs_tol=1e-12) else "sawtooth"
            waveform_term = (kind, float(coefficient), float(frequency), float(phase))
            continue
        if term.free_symbols:
            return None
        numeric_term = _extract_numeric_expr(term)
        if numeric_term is None:
            return None
        bias += numeric_term
    if waveform_term is None:
        return None
    return {
        "kind": waveform_term[0],
        "amplitude": waveform_term[1],
        "frequency": waveform_term[2],
        "phase": waveform_term[3],
        "bias": float(bias),
        "width": 0.5 if waveform_term[0] == "triangle" else 1.0,
    }


def _match_random_expression(
    expression: sympy.Expr,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    sample_time = max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-3)
    if expression.func == _RAND_FUNCTION and not expression.args:
        return {
            "kind": "random_number",
            "minimum": 0.0,
            "maximum": 1.0,
            "seed": 0,
            "sample_time": sample_time,
        }
    if expression.func == _RANDN_FUNCTION and not expression.args:
        return {
            "kind": "white_noise",
            "mean": 0.0,
            "variance": 1.0,
            "seed": 0,
            "sample_time": sample_time,
        }
    return None


def _match_piecewise_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    if expression.func != sympy.Piecewise:
        return None
    branches: list[dict[str, object]] = []
    otherwise: dict[str, object] | None = None
    for value_expr, condition_expr in expression.args:
        value_spec = _canonicalize_native_expression_tree(value_expr, time_symbol, t_span=t_span)
        if value_spec is None:
            return None
        condition_spec = _canonicalize_condition_spec(condition_expr, "piecewise", time_symbol, t_span=t_span)
        if condition_spec is None:
            return None
        if _is_true_condition(condition_spec):
            otherwise = value_spec
            break
        branches.append({"condition": condition_spec, "value": value_spec})
    if otherwise is None:
        otherwise = {"kind": "constant", "value": 0.0}
    return {"kind": "piecewise", "branches": branches, "otherwise": otherwise}


def _match_dead_zone_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    if expression.func != sympy.Piecewise or len(expression.args) != 3:
        return None
    first_value, first_condition = expression.args[0]
    second_value, second_condition = expression.args[1]
    third_value, third_condition = expression.args[2]
    first_numeric = _extract_numeric_expr(first_value)
    if first_numeric is None or abs(first_numeric) > 1e-12:
        return None
    if third_condition not in {True, sympy.true}:
        return None
    first_match = _extract_abs_bound_condition(first_condition, time_symbol)
    second_match = _extract_signed_bound_condition(second_condition, time_symbol)
    if first_match is None or second_match is None:
        return None
    inner_expr, dead_zone_size = first_match
    second_inner, second_bound, second_sign = second_match
    if not sympy.simplify(inner_expr - second_inner) == 0:
        return None
    if not math.isclose(dead_zone_size, abs(second_bound), rel_tol=0.0, abs_tol=1e-9):
        return None
    if second_sign > 0:
        positive_value = second_value
        negative_value = third_value
    else:
        positive_value = third_value
        negative_value = second_value
    if not sympy.simplify(positive_value - (inner_expr - dead_zone_size)) == 0:
        return None
    if not sympy.simplify(negative_value - (inner_expr + dead_zone_size)) == 0:
        return None
    inner_spec = _canonicalize_native_expression_tree(inner_expr, time_symbol, t_span=t_span)
    if inner_spec is None:
        return None
    return {
        "kind": "dead_zone",
        "input": inner_spec,
        "lower_limit": -float(dead_zone_size),
        "upper_limit": float(dead_zone_size),
    }


def _extract_abs_bound_condition(condition: object, time_symbol: sympy.Symbol) -> tuple[sympy.Expr, float] | None:
    if not isinstance(condition, Relational):
        return None
    if condition.lhs.func == sympy.Abs:
        inner_expr = condition.lhs.args[0]
        bound_value = _extract_numeric_expr(condition.rhs)
    elif condition.rhs.func == sympy.Abs:
        inner_expr = condition.rhs.args[0]
        bound_value = _extract_numeric_expr(condition.lhs)
    else:
        return None
    if bound_value is None:
        return None
    if condition.rel_op not in {"<", "<="}:
        return None
    if inner_expr.free_symbols - {time_symbol}:
        return None
    return inner_expr, abs(float(bound_value))


def _extract_signed_bound_condition(condition: object, time_symbol: sympy.Symbol) -> tuple[sympy.Expr, float, int] | None:
    if not isinstance(condition, Relational):
        return None
    lhs_expr = condition.lhs
    rhs_expr = condition.rhs
    rhs_value = _extract_numeric_expr(rhs_expr)
    if rhs_value is not None and not lhs_expr.free_symbols - {time_symbol}:
        if condition.rel_op in {">", ">="}:
            return lhs_expr, float(rhs_value), 1
        if condition.rel_op in {"<", "<="}:
            return lhs_expr, float(rhs_value), -1
    lhs_value = _extract_numeric_expr(lhs_expr)
    if lhs_value is not None and not rhs_expr.free_symbols - {time_symbol}:
        if condition.rel_op in {">", ">="}:
            return rhs_expr, float(lhs_value), -1
        if condition.rel_op in {"<", "<="}:
            return rhs_expr, float(lhs_value), 1
    return None


def _canonicalize_condition_spec(
    condition: object,
    input_name: str,
    time_symbol: sympy.Symbol,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    if isinstance(condition, bool):
        return {"kind": "boolean", "value": bool(condition)}
    if condition == sympy.true or condition == sympy.false:
        return {"kind": "boolean", "value": bool(condition)}
    if isinstance(condition, Mapping):
        raw_kind = condition.get("kind")
        if not isinstance(raw_kind, str):
            raise DeterministicCompileError(
                f"Runtime input condition spec for {input_name!r} must include a string 'kind'."
            )
        kind = raw_kind.strip().lower()
        if kind == "boolean":
            return {"kind": "boolean", "value": bool(condition.get("value", False))}
        if kind == "compare":
            lhs_spec = _canonicalize_input_spec(input_name, condition.get("lhs"), t_span=t_span)
            rhs_spec = _canonicalize_input_spec(input_name, condition.get("rhs"), t_span=t_span)
            operator = str(condition.get("op", condition.get("operator", ""))).strip()
            if operator not in {"<", "<=", ">", ">=", "==", "!="}:
                raise DeterministicCompileError(
                    f"Runtime input compare condition for {input_name!r} must use a supported operator."
                )
            return {"kind": "compare", "lhs": lhs_spec, "rhs": rhs_spec, "op": operator}
        if kind in {"and", "or"}:
            terms = condition.get("terms")
            if not isinstance(terms, (list, tuple)) or not terms:
                raise DeterministicCompileError(
                    f"Runtime input condition {kind!r} for {input_name!r} must include a non-empty 'terms' list."
                )
            normalized_terms = [
                _canonicalize_condition_spec(term, input_name, time_symbol, t_span=t_span)
                for term in terms
            ]
            if any(term is None for term in normalized_terms):
                return None
            return {"kind": kind, "terms": normalized_terms}
        if kind == "not":
            inner = _canonicalize_condition_spec(condition.get("input"), input_name, time_symbol, t_span=t_span)
            if inner is None:
                return None
            return {"kind": "not", "input": inner}
        raise DeterministicCompileError(
            f"Unsupported runtime input condition kind {kind!r} for {input_name!r}."
        )
    if isinstance(condition, sympy.And):
        terms = [
            _canonicalize_condition_spec(term, input_name, time_symbol, t_span=t_span)
            for term in condition.args
        ]
        if any(term is None for term in terms):
            return None
        return {"kind": "and", "terms": terms}
    if isinstance(condition, sympy.Or):
        terms = [
            _canonicalize_condition_spec(term, input_name, time_symbol, t_span=t_span)
            for term in condition.args
        ]
        if any(term is None for term in terms):
            return None
        return {"kind": "or", "terms": terms}
    if isinstance(condition, sympy.Not):
        inner = _canonicalize_condition_spec(condition.args[0], input_name, time_symbol, t_span=t_span)
        if inner is None:
            return None
        return {"kind": "not", "input": inner}
    if isinstance(condition, Relational):
        lhs_spec = _canonicalize_native_expression_tree(condition.lhs, time_symbol, t_span=t_span)
        rhs_spec = _canonicalize_native_expression_tree(condition.rhs, time_symbol, t_span=t_span)
        if lhs_spec is None or rhs_spec is None:
            return None
        operator = "!=" if condition.rel_op == "<>" else condition.rel_op
        if operator not in {"<", "<=", ">", ">=", "==", "!="}:
            return None
        return {"kind": "compare", "lhs": lhs_spec, "rhs": rhs_spec, "op": operator}
    return None


def _is_true_condition(spec: Mapping[str, object]) -> bool:
    return str(spec.get("kind", "")) == "boolean" and bool(spec.get("value", False))


def _match_step_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
) -> dict[str, object] | None:
    expanded = sympy.expand(expression)
    step_terms: list[dict[str, object]] = []
    bias = 0.0
    for term in sympy.Add.make_args(expanded):
        coefficient, remainder = term.as_coeff_Mul()
        if remainder.func == sympy.Heaviside:
            start_time, direction = _extract_step_threshold(remainder.args[0], time_symbol)
            if start_time is None:
                return None
            amplitude = float(coefficient)
            if direction < 0.0:
                bias += amplitude
                amplitude = -amplitude
            step_terms.append(
                {
                    "kind": "step",
                    "amplitude": float(amplitude),
                    "start_time": float(start_time),
                    "bias": 0.0,
                }
            )
            continue
        if term.free_symbols:
            return None
        numeric_term = _extract_numeric_expr(term)
        if numeric_term is None:
            return None
        bias += numeric_term
    if not step_terms:
        return None
    step_terms.sort(key=lambda term: (float(term["start_time"]), float(term["amplitude"])))
    if len(step_terms) == 1:
        return {
            "kind": "step",
            "amplitude": float(step_terms[0]["amplitude"]),
            "start_time": float(step_terms[0]["start_time"]),
            "bias": float(bias),
        }
    terms: list[dict[str, object]] = list(step_terms)
    if abs(bias) > 1e-12:
        terms.insert(0, {"kind": "constant", "value": float(bias)})
    return {"kind": "sum", "terms": terms}


def _match_sine_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
) -> dict[str, object] | None:
    expanded = sympy.expand(expression)
    sine_term: tuple[float, float, float] | None = None
    bias = 0.0
    for term in sympy.Add.make_args(expanded):
        coefficient, remainder = term.as_coeff_Mul()
        if remainder.func in {sympy.sin, sympy.cos} and len(remainder.args) == 1:
            if sine_term is not None:
                return None
            frequency, phase = _extract_linear_phase(remainder.args[0], time_symbol)
            if frequency is None:
                return None
            if remainder.func == sympy.cos:
                phase += math.pi / 2.0
            sine_term = (float(coefficient), float(frequency), float(phase))
            continue
        if term.free_symbols:
            return None
        numeric_term = _extract_numeric_expr(term)
        if numeric_term is None:
            return None
        bias += numeric_term
    if sine_term is None:
        return None
    return {
        "kind": "sine",
        "amplitude": sine_term[0],
        "frequency": sine_term[1],
        "phase": sine_term[2],
        "bias": float(bias),
    }


def _match_impulse_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    expanded = sympy.expand(expression)
    impulse_terms: list[dict[str, object]] = []
    bias = 0.0
    default_width = max((float(t_span[1]) - float(t_span[0])) / 1000.0, 1e-6)
    for term in sympy.Add.make_args(expanded):
        coefficient, remainder = term.as_coeff_Mul()
        if remainder.func == sympy.DiracDelta and len(remainder.args) >= 1:
            start_time, slope = _extract_step_threshold(remainder.args[0], time_symbol)
            if start_time is None or abs(float(slope)) <= 1e-12:
                return None
            impulse_terms.append(
                {
                    "kind": "impulse",
                    "amplitude": float(coefficient) / abs(float(slope)),
                    "start_time": float(start_time),
                    "width": float(default_width),
                    "period": _default_pulse_period(
                        start_time=float(start_time),
                        width=float(default_width),
                        t_span=t_span,
                    ),
                    "bias": 0.0,
                }
            )
            continue
        if term.free_symbols:
            return None
        numeric_term = _extract_numeric_expr(term)
        if numeric_term is None:
            return None
        bias += numeric_term
    if not impulse_terms:
        return None
    impulse_terms.sort(key=lambda term: (float(term["start_time"]), float(term["amplitude"])))
    if len(impulse_terms) == 1:
        impulse_spec = dict(impulse_terms[0])
        impulse_spec["bias"] = float(bias)
        return impulse_spec
    terms: list[dict[str, object]] = list(impulse_terms)
    if abs(bias) > 1e-12:
        terms.insert(0, {"kind": "constant", "value": float(bias)})
    return {"kind": "sum", "terms": terms}


def _match_ramp_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
) -> dict[str, object] | None:
    expanded = sympy.expand(expression)
    bias = 0.0
    for term in sympy.Add.make_args(expanded):
        if term.has(sympy.Heaviside):
            continue
        if term.free_symbols:
            return None
        numeric_term = _extract_numeric_expr(term)
        if numeric_term is None:
            return None
        bias += numeric_term

    residual = sympy.factor(sympy.simplify(expanded - bias))
    coefficient, factors = residual.as_coeff_mul()
    heaviside_factor = next(
        (factor for factor in factors if getattr(factor, "func", None) == sympy.Heaviside and len(factor.args) >= 1),
        None,
    )
    if heaviside_factor is None:
        return None
    remaining_factors = [factor for factor in factors if factor is not heaviside_factor]
    if len(remaining_factors) != 1:
        return None
    start_time, direction = _extract_step_threshold(heaviside_factor.args[0], time_symbol)
    if start_time is None or direction <= 0.0:
        return None
    linear_slope, linear_intercept = _extract_linear_phase(remaining_factors[0], time_symbol)
    if linear_slope is None:
        return None
    if not math.isclose(float(linear_intercept + linear_slope * start_time), 0.0, rel_tol=0.0, abs_tol=1e-9):
        return None
    return {
        "kind": "ramp",
        "slope": float(coefficient) * float(linear_slope),
        "start_time": float(start_time),
        "initial_output": float(bias),
    }


def _match_saturation_expression(
    expression: sympy.Expr,
    time_symbol: sympy.Symbol,
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    source_expr: sympy.Expr | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None

    if len(expression.args) == 3 and str(expression.func) == "sat":
        source_expr = expression.args[0]
        lower_limit = _extract_numeric_expr(expression.args[1])
        upper_limit = _extract_numeric_expr(expression.args[2])
    elif expression.func == sympy.Min and len(expression.args) == 2:
        numeric_outer = [(index, _extract_numeric_expr(arg)) for index, arg in enumerate(expression.args)]
        outer_candidates = [(index, value) for index, value in numeric_outer if value is not None]
        if len(outer_candidates) == 1:
            outer_index, upper_limit = outer_candidates[0]
            inner = expression.args[1 - outer_index]
            if inner.func == sympy.Max and len(inner.args) == 2:
                lower_candidates = [(idx, _extract_numeric_expr(arg)) for idx, arg in enumerate(inner.args)]
                lower_numeric = [(idx, value) for idx, value in lower_candidates if value is not None]
                if len(lower_numeric) == 1:
                    lower_index, lower_limit = lower_numeric[0]
                    source_expr = inner.args[1 - lower_index]
    elif expression.func == sympy.Max and len(expression.args) == 2:
        numeric_outer = [(index, _extract_numeric_expr(arg)) for index, arg in enumerate(expression.args)]
        outer_candidates = [(index, value) for index, value in numeric_outer if value is not None]
        if len(outer_candidates) == 1:
            outer_index, lower_limit = outer_candidates[0]
            inner = expression.args[1 - outer_index]
            if inner.func == sympy.Min and len(inner.args) == 2:
                upper_candidates = [(idx, _extract_numeric_expr(arg)) for idx, arg in enumerate(inner.args)]
                upper_numeric = [(idx, value) for idx, value in upper_candidates if value is not None]
                if len(upper_numeric) == 1:
                    upper_index, upper_limit = upper_numeric[0]
                    source_expr = inner.args[1 - upper_index]

    if source_expr is None or lower_limit is None or upper_limit is None:
        return None
    if lower_limit > upper_limit:
        return None
    inner_spec = _canonicalize_input_spec(
        "input",
        {"kind": "expression", "expression": str(source_expr), "time_variable": str(time_symbol)},
        t_span=t_span,
    )
    if not _is_native_source_spec(inner_spec):
        return None
    return {
        "kind": "saturation",
        "input": inner_spec,
        "lower_limit": float(lower_limit),
        "upper_limit": float(upper_limit),
    }


def _match_pulse_from_step_spec(
    spec: Mapping[str, object],
    *,
    t_span: tuple[float, float],
) -> dict[str, object] | None:
    if str(spec.get("kind", "")) != "sum":
        return None
    terms = list(spec.get("terms", []))
    step_terms = [term for term in terms if isinstance(term, Mapping) and str(term.get("kind", "")) == "step"]
    constant_terms = [term for term in terms if isinstance(term, Mapping) and str(term.get("kind", "")) == "constant"]
    if len(step_terms) != 2 or len(step_terms) + len(constant_terms) != len(terms):
        return None

    first, second = sorted(step_terms, key=lambda item: float(item.get("start_time", 0.0)))
    amplitude = float(first.get("amplitude", 0.0))
    if not math.isclose(float(second.get("amplitude", 0.0)), -amplitude, rel_tol=0.0, abs_tol=1e-12):
        return None
    start_time = float(first.get("start_time", 0.0))
    stop_time = float(second.get("start_time", 0.0))
    width = stop_time - start_time
    if width <= 0.0:
        return None
    bias = sum(float(term.get("value", 0.0)) for term in constant_terms)
    return {
        "kind": "pulse",
        "amplitude": amplitude,
        "start_time": start_time,
        "width": width,
        "period": _default_pulse_period(start_time=start_time, width=width, t_span=t_span),
        "bias": bias,
    }


def _extract_step_threshold(argument: sympy.Expr, time_symbol: sympy.Symbol) -> tuple[float | None, float]:
    slope, intercept = _extract_linear_phase(argument, time_symbol)
    if slope is None or abs(float(slope)) <= 1e-12:
        return None, 0.0
    return float(-intercept / slope), float(slope)


def _extract_linear_phase(argument: sympy.Expr, time_symbol: sympy.Symbol) -> tuple[float | None, float]:
    expanded = sympy.expand(argument)
    derivative = sympy.diff(expanded, time_symbol)
    if derivative.free_symbols:
        return None, 0.0
    slope = float(derivative)
    intercept = sympy.simplify(expanded.subs(time_symbol, 0.0))
    if intercept.free_symbols:
        return None, 0.0
    return slope, float(intercept)


def _extract_numeric_expr(argument: object) -> float | None:
    try:
        value = sympy.simplify(argument)
    except Exception:
        return None
    if getattr(value, "free_symbols", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_nested_input_spec(
    spec: Mapping[str, object],
    input_name: str,
    *,
    field_names: tuple[str, ...],
) -> object:
    for field_name in field_names:
        if field_name in spec:
            return spec[field_name]
    raise DeterministicCompileError(
        f"Runtime input spec for {input_name!r} must include one of {field_names}."
    )


def _is_native_source_spec(spec: Mapping[str, object]) -> bool:
    kind = str(spec.get("kind", ""))
    if kind in _LEAF_NATIVE_SOURCE_KINDS:
        return True
    if kind in {"sum", "product"}:
        terms = spec.get("terms")
        return isinstance(terms, (list, tuple)) and bool(terms) and all(
            isinstance(term, Mapping) and _is_native_source_spec(term) for term in terms
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
        return isinstance(inner, Mapping) and _is_native_source_spec(inner)
    if kind == "binary_trig_function":
        lhs = spec.get("lhs")
        rhs = spec.get("rhs")
        return (
            isinstance(lhs, Mapping)
            and _is_native_source_spec(lhs)
            and isinstance(rhs, Mapping)
            and _is_native_source_spec(rhs)
        )
    if kind == "minmax":
        terms = spec.get("terms")
        return isinstance(terms, (list, tuple)) and bool(terms) and all(
            isinstance(term, Mapping) and _is_native_source_spec(term) for term in terms
        )
    if kind in {"random_number", "white_noise"}:
        return True
    if kind == "piecewise":
        branches = spec.get("branches")
        otherwise = spec.get("otherwise")
        return (
            isinstance(branches, (list, tuple))
            and bool(branches)
            and all(
                isinstance(branch, Mapping)
                and isinstance(branch.get("value"), Mapping)
                and _is_native_source_spec(branch["value"])
                and _is_supported_condition_spec(branch.get("condition"))
                for branch in branches
            )
            and isinstance(otherwise, Mapping)
            and _is_native_source_spec(otherwise)
        )
    return False


def _is_supported_condition_spec(condition: object) -> bool:
    if not isinstance(condition, Mapping):
        return False
    kind = str(condition.get("kind", ""))
    if kind == "boolean":
        return isinstance(condition.get("value"), bool)
    if kind == "compare":
        return (
            str(condition.get("op", "")) in {"<", "<=", ">", ">=", "==", "!="}
            and isinstance(condition.get("lhs"), Mapping)
            and _is_native_source_spec(condition["lhs"])
            and isinstance(condition.get("rhs"), Mapping)
            and _is_native_source_spec(condition["rhs"])
        )
    if kind in {"and", "or"}:
        terms = condition.get("terms")
        return isinstance(terms, (list, tuple)) and bool(terms) and all(_is_supported_condition_spec(term) for term in terms)
    if kind == "not":
        return _is_supported_condition_spec(condition.get("input"))
    return False


def _pulse_is_active(time_value: float, *, start_time: float, width: float, period: float) -> bool:
    if time_value < start_time:
        return False
    if period <= 0.0:
        return False
    phase = math.fmod(time_value - start_time, period)
    if phase < 0.0:
        phase += period
    return phase < width


def _default_pulse_period(
    *,
    start_time: float,
    width: float,
    t_span: tuple[float, float],
) -> float:
    simulation_end = float(t_span[1])
    return max(width * 2.0, (simulation_end - start_time) + width + max(width, 1.0))


def _numeric_field(
    spec: Mapping[str, object],
    input_name: str,
    *,
    names: tuple[str, ...],
    default: float,
) -> float:
    for name in names:
        if name in spec:
            raw_value = spec[name]
            try:
                return float(raw_value)
            except (TypeError, ValueError) as exc:
                raise DeterministicCompileError(
                    f"Runtime input spec field {input_name!r}.{name} must be numeric."
                ) from exc
    return float(default)


def _sawtooth_wave(argument: float, *, width: float) -> float:
    normalized_width = min(max(float(width), 1e-6), 1.0)
    period = 2.0 * math.pi
    phase = math.fmod(float(argument), period)
    if phase < 0.0:
        phase += period
    cycle = phase / period
    if cycle < normalized_width:
        return -1.0 + (2.0 * cycle / normalized_width)
    falling_width = 1.0 - normalized_width
    if falling_width <= 1e-12:
        return -1.0
    return 1.0 - (2.0 * (cycle - normalized_width) / falling_width)


def _dead_zone_value(value: float, *, lower_limit: float, upper_limit: float) -> float:
    if value > upper_limit:
        return float(value - upper_limit)
    if value < lower_limit:
        return float(value - lower_limit)
    return 0.0


def _sign_value(value: float) -> float:
    if value > 0.0:
        return 1.0
    if value < 0.0:
        return -1.0
    return 0.0


def _compile_condition_spec(
    condition: object,
    input_name: str,
    *,
    t_span: tuple[float, float],
):
    if condition is None:
        raise DeterministicCompileError(
            f"Runtime input condition for {input_name!r} could not be canonicalized."
        )
    if not isinstance(condition, Mapping):
        raise DeterministicCompileError(
            f"Runtime input condition for {input_name!r} must be a condition object."
        )
    kind = str(condition.get("kind", ""))
    if kind == "boolean":
        value = bool(condition.get("value", False))
        return lambda _time: value
    if kind == "compare":
        lhs = condition.get("lhs")
        rhs = condition.get("rhs")
        if not isinstance(lhs, Mapping) or not isinstance(rhs, Mapping):
            raise DeterministicCompileError(
                f"Runtime input compare condition for {input_name!r} must include 'lhs' and 'rhs' sources."
            )
        lhs_evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, lhs, t_span=t_span),
            t_span=t_span,
        )
        rhs_evaluator = _compile_canonical_input_spec(
            input_name,
            _canonicalize_input_spec(input_name, rhs, t_span=t_span),
            t_span=t_span,
        )
        operator = str(condition.get("op", ""))
        if operator == "<":
            return lambda time_value: lhs_evaluator(time_value) < rhs_evaluator(time_value)
        if operator == "<=":
            return lambda time_value: lhs_evaluator(time_value) <= rhs_evaluator(time_value)
        if operator == ">":
            return lambda time_value: lhs_evaluator(time_value) > rhs_evaluator(time_value)
        if operator == ">=":
            return lambda time_value: lhs_evaluator(time_value) >= rhs_evaluator(time_value)
        if operator == "==":
            return lambda time_value: math.isclose(
                lhs_evaluator(time_value),
                rhs_evaluator(time_value),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        if operator == "!=":
            return lambda time_value: not math.isclose(
                lhs_evaluator(time_value),
                rhs_evaluator(time_value),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        raise DeterministicCompileError(
            f"Runtime input compare condition for {input_name!r} uses unsupported operator {operator!r}."
        )
    if kind in {"and", "or"}:
        terms = condition.get("terms")
        if not isinstance(terms, (list, tuple)) or not terms:
            raise DeterministicCompileError(
                f"Runtime input condition {kind!r} for {input_name!r} must include a non-empty 'terms' list."
            )
        evaluators = [_compile_condition_spec(term, input_name, t_span=t_span) for term in terms]
        if kind == "and":
            return lambda time_value: all(evaluator(time_value) for evaluator in evaluators)
        return lambda time_value: any(evaluator(time_value) for evaluator in evaluators)
    if kind == "not":
        inner = _compile_condition_spec(condition.get("input"), input_name, t_span=t_span)
        return lambda time_value: not inner(time_value)
    raise DeterministicCompileError(
        f"Runtime input condition for {input_name!r} uses unsupported kind {kind!r}."
    )


def _deterministic_noise_function(
    *,
    mean: float,
    variance: float,
    seed: int,
    sample_time: float,
    gaussian: bool,
    minimum: float = 0.0,
    maximum: float = 1.0,
):
    if sample_time <= 0.0:
        raise DeterministicCompileError("Deterministic noise sample_time must be positive.")
    if variance < 0.0:
        raise DeterministicCompileError("Deterministic noise variance must be non-negative.")
    if minimum > maximum:
        raise DeterministicCompileError("Deterministic uniform noise minimum must be <= maximum.")
    generator = random.Random(int(seed))
    cache: dict[int, float] = {}

    def _sample(index: int) -> float:
        if index not in cache:
            if gaussian:
                cache[index] = float(generator.gauss(mean, math.sqrt(variance)))
            else:
                cache[index] = float(generator.uniform(minimum, maximum))
        return cache[index]

    return lambda time_value: _sample(int(math.floor(float(time_value) / sample_time + 1e-12)))
