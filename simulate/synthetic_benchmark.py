"""Deterministic synthetic system generator and full benchmark harness."""

from __future__ import annotations

import csv
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from backend.simulate_simulink import SimulinkExecutionStageError, execute_simulink_graph
from ir.equation_dict import equation_to_string
from latex_frontend.symbols import DeterministicCompileError, state_name
from latex_frontend.translator import translate_latex
from pipeline.compilation import SymbolicCompilationStageError, compile_symbolic_system
from repo_paths import DATA_ROOT, GENERATED_MODELS_ROOT, REPORTS_ROOT
from simulate.compare import DEFAULT_TOLERANCE, compare_simulations
from simulate.ode_sim import constant_inputs, simulate_ode_system
from simulate.state_space_sim import simulate_state_space_system
from simulink.engine import start_engine


STATE_VARS = [f"x_{index}" for index in range(1, 7)]
INPUT_VARS = ["u"]
PARAMS = ["a", "b", "c", "k", "m"]
CONSTANTS = ["1", "2", "3"]
OPS = ["add", "mul", "pow", "sin", "cos"]
DEFAULT_SYNTHETIC_SYSTEM_COUNT = 216
DEFAULT_SYNTHETIC_SEED = 20260318


def _stage(status: str, detail: str | None = None) -> dict[str, object]:
    return {"status": status, "detail": detail}


def _default_stages() -> dict[str, dict[str, object]]:
    return {
        "parse": _stage("skipped"),
        "state_extraction": _stage("skipped"),
        "solve": _stage("skipped"),
        "first_order": _stage("skipped"),
        "state_space": _stage("skipped"),
        "graph_lowering": _stage("skipped"),
        "graph_validation": _stage("skipped"),
        "ode_simulation": _stage("skipped"),
        "state_space_simulation": _stage("skipped"),
        "state_space_compare": _stage("skipped"),
        "simulink_build": _stage("skipped"),
        "simulink_simulation": _stage("skipped"),
        "simulink_compare": _stage("skipped"),
    }


def _mean(values: Iterable[float | None]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return float(sum(filtered) / len(filtered))


def _derivative_latex(name: str, order: int) -> str:
    if order == 1:
        return rf"\dot{{{name}}}"
    if order == 2:
        return rf"\ddot{{{name}}}"
    return rf"\frac{{d^{order} {name}}}{{dt^{order}}}"


def _join_terms(terms: list[str]) -> str:
    if not terms:
        return "0"
    expr = terms[0]
    for term in terms[1:]:
        if term.startswith("-"):
            expr += term
        else:
            expr += f"+{term}"
    return expr


def _random_expr(
    rng: random.Random,
    symbols: list[str],
    depth: int,
    *,
    include_trig: bool,
) -> str:
    if depth <= 0:
        return rng.choice(symbols + CONSTANTS)

    ops = ["add", "mul", "pow"]
    if include_trig:
        ops.extend(["sin", "cos"])
    op = rng.choice(ops)

    if op == "add":
        left = _random_expr(rng, symbols, depth - 1, include_trig=include_trig)
        right = _random_expr(rng, symbols, depth - 1, include_trig=include_trig)
        return f"({left}+{right})"
    if op == "mul":
        left = _random_expr(rng, symbols, depth - 1, include_trig=False)
        right = _random_expr(rng, symbols, depth - 1, include_trig=False)
        return f"({left}*{right})"
    if op == "pow":
        base = _random_expr(rng, symbols, depth - 1, include_trig=False)
        return f"({base})^2"
    if op == "sin":
        inner = _random_expr(rng, symbols, depth - 1, include_trig=False)
        return rf"\sin({inner})"
    if op == "cos":
        inner = _random_expr(rng, symbols, depth - 1, include_trig=False)
        return rf"\cos({inner})"
    raise DeterministicCompileError(f"Unsupported synthetic expression op {op!r}.")


def _parameter_values(generated_state_count: int, depth: int, family_index: int) -> dict[str, float]:
    return {
        "a": round(0.22 + 0.03 * ((generated_state_count + family_index) % 4), 6),
        "b": round(0.07 + 0.02 * ((depth + family_index) % 4), 6),
        "c": round(0.05 + 0.015 * ((generated_state_count + depth) % 4), 6),
        "k": round(0.12 + 0.025 * ((generated_state_count + 2 * family_index) % 5), 6),
        "m": round(0.55 + 0.05 * ((generated_state_count + depth + family_index) % 4), 6),
    }


def _family_name(index: int) -> str:
    family_names = {
        0: "linear_first_order",
        1: "linear_dense_coupled",
        2: "nonlinear_polynomial",
        3: "nonlinear_trigonometric",
        4: "linear_mixed_order",
        5: "nonlinear_mixed_order",
    }
    return family_names[index]


def _family_flags(index: int) -> tuple[bool, bool]:
    nonlinear = index in {2, 3, 5}
    trig = index in {3, 5}
    return nonlinear, trig


def _order_map_for_family(states: list[str], depth: int, family_index: int) -> dict[str, int]:
    order_map = {name: 1 for name in states}
    if family_index in {4, 5}:
        order_map[states[0]] = 3 if depth >= 3 else 2
    return order_map


def _initial_conditions(order_map: dict[str, int], generated_state_count: int, depth: int, family_index: int) -> dict[str, float]:
    values: dict[str, float] = {}
    for index, base in enumerate(order_map):
        sign = -1.0 if (index + depth + family_index) % 2 else 1.0
        base_value = sign * (0.04 + 0.01 * ((generated_state_count + index) % 4))
        values[state_name(base, 0)] = round(base_value, 6)
        max_order = order_map[base]
        for order in range(1, max_order):
            derivative_value = sign * (0.01 * order)
            values[state_name(base, order)] = round(derivative_value, 6)
    return values


def _runtime_shape(generated_state_count: int, depth: int, family_index: int) -> tuple[tuple[float, float], int]:
    stop = 2.5 + 0.5 * ((generated_state_count + family_index) % 3)
    sample_count = 90 + 10 * depth
    if generated_state_count >= 5:
        sample_count -= 10
    return (0.0, float(stop)), int(sample_count)


def _expression_depth(generated_state_count: int, depth: int, family_index: int) -> int:
    """Cap nonlinear expression complexity for larger systems to keep the benchmark tractable."""
    if family_index in {2, 3, 5}:
        depth = min(depth, 2)
        if generated_state_count >= 4:
            return 1
    return depth


def _linear_rhs(
    states: list[str],
    index: int,
    *,
    depth: int,
    include_input: bool,
    dense: bool,
) -> str:
    state = states[index]
    terms = [f"-a*{state}"]
    neighbour = states[(index + 1) % len(states)]
    if neighbour != state:
        terms.append(f"b*{neighbour}")
    if dense and len(states) > 2 and depth >= 2:
        neighbour2 = states[(index + 2) % len(states)]
        if neighbour2 != state:
            sign = "-" if (index + depth) % 2 else ""
            terms.append(f"{sign}c*{neighbour2}")
    if dense and depth >= 3 and len(states) > 3:
        neighbour3 = states[(index + 3) % len(states)]
        if neighbour3 != state:
            terms.append(f"k*{neighbour3}")
    if include_input and index % 2 == 0:
        terms.append("b*u")
    return _join_terms(terms)


def _polynomial_rhs(
    rng: random.Random,
    states: list[str],
    index: int,
    *,
    depth: int,
    include_input: bool,
) -> str:
    state = states[index]
    symbols = list(states)
    if include_input:
        symbols.append("u")
    poly_source = _random_expr(rng, symbols, max(depth - 1, 0), include_trig=False)
    neighbour = states[(index + 1) % len(states)]
    terms = [
        f"-a*{state}",
        f"(3/100)*(({poly_source})^2)",
        f"(1/50)*({state}*{neighbour})",
    ]
    if include_input:
        terms.append("b*u")
    return _join_terms(terms)


def _trig_rhs(
    rng: random.Random,
    states: list[str],
    index: int,
    *,
    depth: int,
    include_input: bool,
) -> str:
    state = states[index]
    symbols = list(states)
    if include_input:
        symbols.append("u")
    arg1 = _random_expr(rng, symbols, depth, include_trig=False)
    arg2 = _random_expr(rng, symbols, max(depth - 1, 0), include_trig=False)
    terms = [
        f"-a*{state}",
        rf"(3/20)*\sin({arg1})",
        rf"(2/25)*\cos({arg2})",
    ]
    if depth >= 2:
        terms.append(f"(1/100)*(({state})^2)")
    if include_input:
        terms.append("c*u")
    return _join_terms(terms)


def _mixed_order_equation(
    rng: random.Random,
    states: list[str],
    *,
    depth: int,
    include_input: bool,
    nonlinear: bool,
) -> str:
    head = states[0]
    order = 3 if depth >= 3 else 2
    derivative = _derivative_latex(head, order)
    if order == 2:
        terms = [f"-a*{_derivative_latex(head, 1)}", f"-b*{head}"]
        if len(states) > 1:
            terms.append(f"c*{states[1]}")
        if nonlinear:
            arg = _random_expr(rng, list(states) + (["u"] if include_input else []), depth, include_trig=False)
            terms.append(rf"(3/25)*\sin({arg})")
        if include_input:
            terms.append("u")
        return f"{derivative}={_join_terms(terms)}"

    terms = [
        f"-a*{_derivative_latex(head, 2)}",
        f"-b*{_derivative_latex(head, 1)}",
        f"-c*{head}",
    ]
    if len(states) > 1:
        terms.append(f"k*{states[1]}")
    if nonlinear:
        arg = _random_expr(rng, list(states) + (["u"] if include_input else []), depth, include_trig=False)
        terms.append(rf"(1/10)*\cos({arg})")
    if include_input:
        terms.append("u")
    return f"{derivative}={_join_terms(terms)}"


@dataclass(frozen=True)
class SyntheticSystemSpec:
    """Single deterministic synthetic system."""

    system_id: str
    family: str
    latex: str
    generated_state_count: int
    max_order: int
    depth: int
    includes_trig: bool
    nonlinear: bool
    parameter_values: dict[str, float]
    initial_conditions: dict[str, float]
    input_values: dict[str, float]
    symbol_config: dict[str, str]
    t_span: tuple[float, float]
    sample_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "system_id": self.system_id,
            "family": self.family,
            "latex": self.latex,
            "generated_state_count": self.generated_state_count,
            "max_order": self.max_order,
            "depth": self.depth,
            "includes_trig": self.includes_trig,
            "nonlinear": self.nonlinear,
            "parameter_values": self.parameter_values,
            "initial_conditions": self.initial_conditions,
            "input_values": self.input_values,
            "symbol_config": self.symbol_config,
            "t_span": list(self.t_span),
            "sample_count": self.sample_count,
        }


def _build_spec(
    system_id: str,
    generated_state_count: int,
    depth: int,
    include_input: bool,
    family_index: int,
    rng: random.Random,
) -> SyntheticSystemSpec:
    states = STATE_VARS[:generated_state_count]
    nonlinear, trig = _family_flags(family_index)
    parameter_values = _parameter_values(generated_state_count, depth, family_index)
    order_map = _order_map_for_family(states, depth, family_index)
    initial_conditions = _initial_conditions(order_map, generated_state_count, depth, family_index)
    t_span, sample_count = _runtime_shape(generated_state_count, depth, family_index)
    expression_depth = _expression_depth(generated_state_count, depth, family_index)
    input_values = {"u": round(0.12 + 0.03 * depth, 6)} if include_input else {}
    symbol_config = {name: "parameter" for name in PARAMS}
    symbol_config["u"] = "input"

    equations: list[str] = []
    if family_index == 0:
        for index in range(generated_state_count):
            equations.append(rf"\dot{{{states[index]}}}={_linear_rhs(states, index, depth=depth, include_input=include_input, dense=False)}")
    elif family_index == 1:
        for index in range(generated_state_count):
            equations.append(rf"\dot{{{states[index]}}}={_linear_rhs(states, index, depth=depth, include_input=include_input, dense=True)}")
    elif family_index == 2:
        for index in range(generated_state_count):
            equations.append(
                rf"\dot{{{states[index]}}}="
                f"{_polynomial_rhs(rng, states, index, depth=expression_depth, include_input=include_input)}"
            )
    elif family_index == 3:
        for index in range(generated_state_count):
            equations.append(
                rf"\dot{{{states[index]}}}="
                f"{_trig_rhs(rng, states, index, depth=expression_depth, include_input=include_input)}"
            )
    elif family_index == 4:
        equations.append(_mixed_order_equation(rng, states, depth=depth, include_input=include_input, nonlinear=False))
        for index in range(1, generated_state_count):
            equations.append(rf"\dot{{{states[index]}}}={_linear_rhs(states, index, depth=depth, include_input=include_input, dense=True)}")
    elif family_index == 5:
        equations.append(
            _mixed_order_equation(
                rng,
                states,
                depth=expression_depth,
                include_input=include_input,
                nonlinear=True,
            )
        )
        for index in range(1, generated_state_count):
            rhs = _trig_rhs(rng, states, index, depth=max(1, expression_depth - 1), include_input=include_input)
            equations.append(rf"\dot{{{states[index]}}}={rhs}")
    else:
        raise DeterministicCompileError(f"Unsupported synthetic family index {family_index}.")

    return SyntheticSystemSpec(
        system_id=system_id,
        family=_family_name(family_index),
        latex="\n".join(equations),
        generated_state_count=generated_state_count,
        max_order=max(order_map.values()),
        depth=depth,
        includes_trig=trig,
        nonlinear=nonlinear,
        parameter_values=parameter_values,
        initial_conditions=initial_conditions,
        input_values=input_values,
        symbol_config=symbol_config,
        t_span=t_span,
        sample_count=sample_count,
    )


def generate_synthetic_systems(
    count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    *,
    seed: int = DEFAULT_SYNTHETIC_SEED,
) -> list[SyntheticSystemSpec]:
    """Generate a deterministic synthetic dataset of dynamical systems."""
    if count < 1:
        raise DeterministicCompileError("Synthetic benchmark count must be at least 1.")

    systems: list[SyntheticSystemSpec] = []
    for depth in (1, 2, 3):
        for include_input in (False, True):
            for generated_state_count in range(1, 7):
                for family_index in range(6):
                    if len(systems) >= count:
                        return systems
                    combo_index = len(systems)
                    rng = random.Random(seed + combo_index * 10007)
                    system_id = (
                        f"syn_s{generated_state_count}_d{depth}_u{int(include_input)}_f{family_index}"
                    )
                    systems.append(
                        _build_spec(
                            system_id,
                            generated_state_count,
                            depth,
                            include_input,
                            family_index,
                            rng,
                        )
                    )

    while len(systems) < count:
        combo_index = len(systems)
        generated_state_count = 1 + (combo_index % 6)
        depth = 1 + ((combo_index // 6) % 3)
        include_input = bool((combo_index // 18) % 2)
        family_index = combo_index % 6
        rng = random.Random(seed + combo_index * 10007)
        system_id = f"syn_extra_{combo_index:03d}"
        systems.append(
            _build_spec(
                system_id,
                generated_state_count,
                depth,
                include_input,
                family_index,
                rng,
            )
        )
    return systems


def _validate_numeric_result(name: str, result: dict[str, object]) -> None:
    states = np.asarray(result["states"], dtype=float)
    if not np.isfinite(states).all():
        raise RuntimeError(f"{name} produced non-finite state values.")


def _flatten_stage_flags(stages: dict[str, dict[str, object]]) -> dict[str, bool]:
    return {
        "parse_success": stages["parse"]["status"] == "passed",
        "state_extraction_success": stages["state_extraction"]["status"] == "passed",
        "solve_success": stages["solve"]["status"] == "passed",
        "first_order_success": stages["first_order"]["status"] == "passed",
        "state_space_success": stages["state_space"]["status"] == "passed",
        "graph_success": stages["graph_lowering"]["status"] == "passed"
        and stages["graph_validation"]["status"] == "passed",
        "simulink_build_success": stages["simulink_build"]["status"] == "passed",
        "simulation_success": stages["ode_simulation"]["status"] == "passed"
        and stages["simulink_simulation"]["status"] in {"passed", "skipped"},
    }


def _failure_category(failure_stage: str | None, failure_reason: str | None) -> str | None:
    if failure_stage is None:
        return None
    if failure_stage == "parse":
        return "parsing failure"
    if failure_stage in {"solve", "state_extraction", "first_order", "state_space"}:
        return "solver failure"
    if failure_stage in {"graph_lowering", "graph_validation"}:
        return "graph failure"
    if failure_stage in {"simulink_build", "simulink_simulation", "simulink_compare"}:
        return "simulink failure"
    if failure_stage in {"ode_simulation", "state_space_simulation", "state_space_compare"}:
        reason = (failure_reason or "").lower()
        if "non-finite" in reason or "nan" in reason or "inf" in reason or "diverg" in reason:
            return "simulation divergence"
        return "simulation failure"
    return "other failure"


def _result_row(
    spec: SyntheticSystemSpec,
    *,
    stages: dict[str, dict[str, object]],
    failure_stage: str | None,
    failure_reason: str | None,
    normalized_equations: list[str] | None,
    extracted_state_count: int | None,
    graph_node_count: int | None,
    simulink_block_count: int | None,
    ode_simulation_time_sec: float | None,
    state_space_simulation_time_sec: float | None,
    simulink_build_time_sec: float | None,
    simulink_simulation_time_sec: float | None,
    state_space_rmse: float | None,
    state_space_max_abs_error: float | None,
    simulink_rmse: float | None,
    simulink_max_abs_error: float | None,
) -> dict[str, object]:
    primary_rmse = simulink_rmse if simulink_rmse is not None else state_space_rmse
    primary_max = simulink_max_abs_error if simulink_max_abs_error is not None else state_space_max_abs_error
    stage_flags = _flatten_stage_flags(stages)
    state_space_ok = (
        stages["state_space"]["status"] in {"passed", "skipped"}
        and stages["state_space_simulation"]["status"] in {"passed", "skipped"}
        and stages["state_space_compare"]["status"] in {"passed", "skipped"}
    )
    simulink_ok = (
        stages["simulink_build"]["status"] in {"passed", "skipped"}
        and stages["simulink_simulation"]["status"] in {"passed", "skipped"}
        and stages["simulink_compare"]["status"] in {"passed", "skipped"}
    )
    overall_pass = (
        stages["parse"]["status"] == "passed"
        and stages["state_extraction"]["status"] == "passed"
        and stages["solve"]["status"] == "passed"
        and stages["first_order"]["status"] == "passed"
        and stages["graph_lowering"]["status"] == "passed"
        and stages["graph_validation"]["status"] == "passed"
        and stages["ode_simulation"]["status"] == "passed"
        and state_space_ok
        and simulink_ok
    )
    if overall_pass:
        failure_stage = None
        failure_reason = None

    return {
        "system_id": spec.system_id,
        "family": spec.family,
        "latex": spec.latex,
        "generated_state_count": spec.generated_state_count,
        "order": spec.max_order,
        "depth": spec.depth,
        "nonlinear": spec.nonlinear,
        "trig": spec.includes_trig,
        "expected_input": bool(spec.input_values),
        "normalized_equations": normalized_equations,
        "extracted_state_count": extracted_state_count,
        "graph_node_count": graph_node_count,
        "simulink_block_count": simulink_block_count,
        "ode_simulation_time_sec": ode_simulation_time_sec,
        "state_space_simulation_time_sec": state_space_simulation_time_sec,
        "build_time_sec": simulink_build_time_sec,
        "simulation_time_sec": simulink_simulation_time_sec,
        "rmse": primary_rmse,
        "max_abs_error": primary_max,
        "state_space_rmse": state_space_rmse,
        "state_space_max_abs_error": state_space_max_abs_error,
        "simulink_rmse": simulink_rmse,
        "simulink_max_abs_error": simulink_max_abs_error,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "failure_category": _failure_category(failure_stage, failure_reason),
        "stages": stages,
        "overall_pass": overall_pass,
        **stage_flags,
    }


def run_synthetic_benchmark(
    systems: list[SyntheticSystemSpec] | None = None,
    *,
    count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    seed: int = DEFAULT_SYNTHETIC_SEED,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
    progress_callback: Callable[[int, int, dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Evaluate the synthetic systems through the full deterministic pipeline."""
    systems = list(systems or generate_synthetic_systems(count=count, seed=seed))
    total = len(systems)

    eng = None
    engine_error: str | None = None
    if run_simulink:
        try:
            eng = start_engine(retries=1, retry_delay_seconds=1.0)
        except Exception as exc:  # pragma: no cover - environment dependent
            engine_error = str(exc)

    results: list[dict[str, object]] = []
    try:
        for index, spec in enumerate(systems, start=1):
            stages = _default_stages()
            failure_stage = None
            failure_reason = None
            normalized_equations: list[str] | None = None
            extracted_state_count = None
            graph_node_count = None
            simulink_block_count = None
            ode_simulation_time_sec = None
            state_space_simulation_time_sec = None
            simulink_build_time_sec = None
            simulink_simulation_time_sec = None
            state_space_rmse = None
            state_space_max_abs_error = None
            simulink_rmse = None
            simulink_max_abs_error = None

            equations = None
            first_order = None
            state_space = None
            ode_result = None
            state_space_result = None

            try:
                equations = translate_latex(spec.latex)
                normalized_equations = [equation_to_string(item) for item in equations]
                stages["parse"] = _stage("passed")

                try:
                    compilation = compile_symbolic_system(
                        equations,
                        graph_name=spec.system_id,
                        classification_mode="configured",
                        symbol_config=spec.symbol_config,
                        validate_graph=True,
                    )
                except SymbolicCompilationStageError as exc:
                    failure_stage = exc.stage
                    failure_reason = str(exc)
                    for stage_name in exc.completed_stages:
                        stages[stage_name] = _stage("passed")
                    if "state_space" in exc.completed_stages and exc.linearity is not None:
                        if exc.linearity["is_linear"]:
                            stages["state_space"] = _stage("passed")
                        else:
                            stages["state_space"] = _stage("skipped", "nonlinear explicit system")
                    stages[exc.stage] = _stage("failed", failure_reason)
                    result = _result_row(
                        spec,
                        stages=stages,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        normalized_equations=normalized_equations,
                        extracted_state_count=extracted_state_count,
                        graph_node_count=graph_node_count,
                        simulink_block_count=simulink_block_count,
                        ode_simulation_time_sec=ode_simulation_time_sec,
                        state_space_simulation_time_sec=state_space_simulation_time_sec,
                        simulink_build_time_sec=simulink_build_time_sec,
                        simulink_simulation_time_sec=simulink_simulation_time_sec,
                        state_space_rmse=state_space_rmse,
                        state_space_max_abs_error=state_space_max_abs_error,
                        simulink_rmse=simulink_rmse,
                        simulink_max_abs_error=simulink_max_abs_error,
                    )
                    results.append(result)
                    if progress_callback is not None:
                        progress_callback(index, total, result)
                    continue

                extraction = compilation.extraction
                first_order = compilation.first_order
                state_space = compilation.state_space
                graph = compilation.validated_graph or compilation.graph
                extracted_state_count = len(extraction.states)
                graph_node_count = len(compilation.graph["nodes"])
                stages["state_extraction"] = _stage("passed")
                stages["solve"] = _stage("passed")
                stages["first_order"] = _stage("passed")
                if compilation.linearity["is_linear"]:
                    stages["state_space"] = _stage("passed")
                else:
                    stages["state_space"] = _stage("skipped", "nonlinear explicit system")
                stages["graph_lowering"] = _stage("passed")
                stages["graph_validation"] = _stage("passed")

                t_eval = np.linspace(spec.t_span[0], spec.t_span[1], spec.sample_count)
                input_function = constant_inputs(spec.input_values)

                ode_start = time.perf_counter()
                ode_result = simulate_ode_system(
                    first_order,
                    parameter_values=spec.parameter_values,
                    initial_conditions=spec.initial_conditions,
                    input_function=input_function,
                    t_span=spec.t_span,
                    t_eval=t_eval,
                )
                ode_simulation_time_sec = time.perf_counter() - ode_start
                _validate_numeric_result("ODE simulation", ode_result)
                stages["ode_simulation"] = _stage("passed")

                if state_space is not None:
                    try:
                        state_space_start = time.perf_counter()
                        state_space_result = simulate_state_space_system(
                            state_space,
                            parameter_values=spec.parameter_values,
                            initial_conditions=spec.initial_conditions,
                            input_function=input_function,
                            t_span=spec.t_span,
                            t_eval=t_eval,
                        )
                        state_space_simulation_time_sec = time.perf_counter() - state_space_start
                        _validate_numeric_result("state-space simulation", state_space_result)
                        stages["state_space_simulation"] = _stage("passed")
                        state_space_comparison = compare_simulations(ode_result, state_space_result, tolerance=tolerance)
                        state_space_rmse = float(state_space_comparison["rmse"])
                        state_space_max_abs_error = float(state_space_comparison["max_abs_error"])
                        if state_space_comparison["passes"]:
                            stages["state_space_compare"] = _stage(
                                "passed",
                                f"rmse={state_space_rmse:.3e}, max={state_space_max_abs_error:.3e}",
                            )
                        else:
                            stages["state_space_compare"] = _stage(
                                "failed",
                                f"rmse={state_space_rmse:.3e}, max={state_space_max_abs_error:.3e}",
                            )
                            failure_stage = failure_stage or "state_space_compare"
                            failure_reason = failure_reason or stages["state_space_compare"]["detail"]  # type: ignore[assignment]
                    except Exception as exc:
                        stages["state_space_simulation"] = _stage("failed", str(exc))
                        stages["state_space_compare"] = _stage("skipped", "state-space simulation failed")
                        failure_stage = failure_stage or "state_space_simulation"
                        failure_reason = failure_reason or str(exc)
                else:
                    stages["state_space_simulation"] = _stage("skipped", "state-space unavailable")
                    stages["state_space_compare"] = _stage("skipped", "state-space unavailable")

                if run_simulink:
                    if engine_error is not None or eng is None:
                        stages["simulink_build"] = _stage("failed", engine_error or "MATLAB engine unavailable")
                        stages["simulink_simulation"] = _stage("skipped", "Simulink build failed")
                        stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                        failure_stage = failure_stage or "simulink_build"
                        failure_reason = failure_reason or engine_error or "MATLAB engine unavailable"
                    else:
                        try:
                            execution = execute_simulink_graph(
                                eng,
                                graph,
                                name=f"{spec.system_id}_simulink",
                                state_names=list(first_order["states"]),  # type: ignore[index]
                                parameter_values=spec.parameter_values,
                                initial_conditions=spec.initial_conditions,
                                t_span=spec.t_span,
                                t_eval=t_eval,
                                input_values=spec.input_values,
                                ode_result=ode_result,
                                state_space_result=state_space_result,
                                tolerance=tolerance,
                                output_dir=GENERATED_MODELS_ROOT / "synthetic_benchmark_models",
                                close_after_run=True,
                                numeric_result_validator=_validate_numeric_result,
                            )
                            simulink_block_count = execution.block_count
                            simulink_build_time_sec = execution.build_time_sec
                            simulink_simulation_time_sec = execution.simulation_time_sec
                            stages["simulink_build"] = _stage("passed", execution.model_file)
                            stages["simulink_simulation"] = _stage("passed")
                            simulink_validation = execution.validation
                            assert simulink_validation is not None
                            simulink_rmse = float(simulink_validation["vs_ode"]["rmse"])
                            simulink_max_abs_error = float(simulink_validation["vs_ode"]["max_abs_error"])
                            if simulink_validation["passes"]:
                                stages["simulink_compare"] = _stage(
                                    "passed",
                                    f"rmse={simulink_rmse:.3e}, max={simulink_max_abs_error:.3e}",
                                )
                            else:
                                stages["simulink_compare"] = _stage(
                                    "failed",
                                    f"rmse={simulink_rmse:.3e}, max={simulink_max_abs_error:.3e}",
                                )
                                failure_stage = failure_stage or "simulink_compare"
                                failure_reason = failure_reason or stages["simulink_compare"]["detail"]  # type: ignore[assignment]
                        except SimulinkExecutionStageError as exc:
                            if exc.stage == "simulink_build":
                                stages["simulink_build"] = _stage("failed", str(exc))
                                stages["simulink_simulation"] = _stage("skipped", "Simulink build failed")
                                stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                                failure_stage = failure_stage or "simulink_build"
                                failure_reason = failure_reason or str(exc)
                            elif exc.stage == "simulink_simulation":
                                stages["simulink_build"] = stages["simulink_build"] if stages["simulink_build"]["status"] == "passed" else _stage("passed")
                                stages["simulink_simulation"] = _stage("failed", str(exc))
                                stages["simulink_compare"] = _stage("skipped", "Simulink simulation failed")
                                failure_stage = failure_stage or "simulink_simulation"
                                failure_reason = failure_reason or str(exc)
                            else:
                                stages["simulink_compare"] = _stage("failed", str(exc))
                                failure_stage = failure_stage or "simulink_compare"
                                failure_reason = failure_reason or str(exc)
                else:
                    stages["simulink_build"] = _stage("skipped", "Simulink benchmark disabled")
                    stages["simulink_simulation"] = _stage("skipped", "Simulink benchmark disabled")
                    stages["simulink_compare"] = _stage("skipped", "Simulink benchmark disabled")
            except Exception as exc:
                failure_reason = failure_reason or str(exc)
                if stages["parse"]["status"] != "passed":
                    failure_stage = failure_stage or "parse"
                    stages["parse"] = _stage("failed", str(exc))
                elif stages["state_extraction"]["status"] != "passed":
                    failure_stage = failure_stage or "state_extraction"
                    stages["state_extraction"] = _stage("failed", str(exc))
                elif stages["solve"]["status"] != "passed":
                    failure_stage = failure_stage or "solve"
                    stages["solve"] = _stage("failed", str(exc))
                elif stages["first_order"]["status"] != "passed":
                    failure_stage = failure_stage or "first_order"
                    stages["first_order"] = _stage("failed", str(exc))
                elif stages["graph_lowering"]["status"] != "passed":
                    failure_stage = failure_stage or "graph_lowering"
                    stages["graph_lowering"] = _stage("failed", str(exc))
                elif stages["graph_validation"]["status"] != "passed":
                    failure_stage = failure_stage or "graph_validation"
                    stages["graph_validation"] = _stage("failed", str(exc))
                elif stages["ode_simulation"]["status"] != "passed":
                    failure_stage = failure_stage or "ode_simulation"
                    stages["ode_simulation"] = _stage("failed", str(exc))
                else:
                    failure_stage = failure_stage or "other"

            result = _result_row(
                spec,
                stages=stages,
                failure_stage=failure_stage,
                failure_reason=failure_reason,
                normalized_equations=normalized_equations,
                extracted_state_count=extracted_state_count,
                graph_node_count=graph_node_count,
                simulink_block_count=simulink_block_count,
                ode_simulation_time_sec=ode_simulation_time_sec,
                state_space_simulation_time_sec=state_space_simulation_time_sec,
                simulink_build_time_sec=simulink_build_time_sec,
                simulink_simulation_time_sec=simulink_simulation_time_sec,
                state_space_rmse=state_space_rmse,
                state_space_max_abs_error=state_space_max_abs_error,
                simulink_rmse=simulink_rmse,
                simulink_max_abs_error=simulink_max_abs_error,
            )
            results.append(result)
            if progress_callback is not None:
                progress_callback(index, total, result)
    finally:
        if eng is not None:
            eng.quit()

    failure_categories: dict[str, int] = {}
    for result in results:
        category = result["failure_category"]
        if category is None:
            continue
        failure_categories[category] = failure_categories.get(category, 0) + 1

    pass_count = sum(1 for result in results if result["overall_pass"])
    by_generated_state_count: dict[str, dict[str, object]] = {}
    for count_value in sorted({int(result["generated_state_count"]) for result in results}):
        subset = [result for result in results if int(result["generated_state_count"]) == count_value]
        by_generated_state_count[str(count_value)] = {
            "systems": len(subset),
            "passed": sum(1 for result in subset if result["overall_pass"]),
            "success_rate": float(sum(1 for result in subset if result["overall_pass"]) / len(subset)),
            "average_graph_nodes": _mean(result["graph_node_count"] for result in subset),
            "average_simulink_blocks": _mean(result["simulink_block_count"] for result in subset),
            "average_build_time_sec": _mean(result["build_time_sec"] for result in subset),
            "average_simulation_time_sec": _mean(result["simulation_time_sec"] for result in subset),
        }

    def _success_breakdown(flag_name: str) -> dict[str, dict[str, object]]:
        values = [False, True]
        breakdown: dict[str, dict[str, object]] = {}
        for value in values:
            subset = [result for result in results if bool(result[flag_name]) is value]
            if not subset:
                continue
            breakdown[str(value).lower()] = {
                "systems": len(subset),
                "passed": sum(1 for result in subset if result["overall_pass"]),
                "success_rate": float(sum(1 for result in subset if result["overall_pass"]) / len(subset)),
            }
        return breakdown

    report = {
        "seed": seed,
        "generated_systems": total,
        "evaluated_systems": len(results),
        "passed_systems": pass_count,
        "failed_systems": len(results) - pass_count,
        "tolerance": tolerance,
        "failure_categories": dict(sorted(failure_categories.items())),
        "success_rate_by_generated_state_count": by_generated_state_count,
        "success_rate_by_nonlinear": _success_breakdown("nonlinear"),
        "success_rate_by_trig": _success_breakdown("trig"),
        "average_rmse": _mean(result["rmse"] for result in results),
        "average_max_abs_error": _mean(result["max_abs_error"] for result in results),
        "average_graph_node_count": _mean(result["graph_node_count"] for result in results),
        "average_simulink_block_count": _mean(result["simulink_block_count"] for result in results),
        "average_build_time_sec": _mean(result["build_time_sec"] for result in results),
        "average_simulation_time_sec": _mean(result["simulation_time_sec"] for result in results),
        "systems": results,
    }
    return report


def render_benchmark_markdown(report: dict[str, object]) -> str:
    """Render the synthetic benchmark summary as Markdown."""
    lines = [
        "# Synthetic Benchmark",
        "",
        f"- generated systems: {report['generated_systems']}",
        f"- evaluated systems: {report['evaluated_systems']}",
        f"- passed systems: {report['passed_systems']}",
        f"- failed systems: {report['failed_systems']}",
        f"- tolerance: {report['tolerance']}",
        "",
        "## Failure Categories",
    ]
    if report["failure_categories"]:
        for category, count in report["failure_categories"].items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Success Rate by Generated State Count",
        ]
    )
    for count_value, entry in report["success_rate_by_generated_state_count"].items():
        lines.append(
            f"- {count_value} states: {entry['passed']}/{entry['systems']} "
            f"({entry['success_rate']:.1%}), avg graph nodes={entry['average_graph_nodes']}, "
            f"avg Simulink blocks={entry['average_simulink_blocks']}, "
            f"avg build time={entry['average_build_time_sec']}, avg sim time={entry['average_simulation_time_sec']}"
        )

    lines.extend(
        [
            "",
            "## Success Rate by Nonlinearity",
        ]
    )
    for label, entry in report["success_rate_by_nonlinear"].items():
        lines.append(f"- nonlinear={label}: {entry['passed']}/{entry['systems']} ({entry['success_rate']:.1%})")

    lines.extend(
        [
            "",
            "## Success Rate by Trigonometric Content",
        ]
    )
    for label, entry in report["success_rate_by_trig"].items():
        lines.append(f"- trig={label}: {entry['passed']}/{entry['systems']} ({entry['success_rate']:.1%})")

    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            f"- average RMSE: {report['average_rmse']}",
            f"- average max abs error: {report['average_max_abs_error']}",
            f"- average graph node count: {report['average_graph_node_count']}",
            f"- average Simulink block count: {report['average_simulink_block_count']}",
            f"- average build time sec: {report['average_build_time_sec']}",
            f"- average simulation time sec: {report['average_simulation_time_sec']}",
            "",
            "## System Results",
        ]
    )

    for result in report["systems"]:
        lines.append(f"### {result['system_id']}")
        lines.append(f"- family: {result['family']}")
        lines.append(f"- overall_pass: {result['overall_pass']}")
        lines.append(f"- generated_state_count: {result['generated_state_count']}")
        lines.append(f"- order: {result['order']}")
        lines.append(f"- depth: {result['depth']}")
        lines.append(f"- nonlinear: {result['nonlinear']}")
        lines.append(f"- trig: {result['trig']}")
        lines.append(f"- rmse: {result['rmse']}")
        lines.append(f"- max_abs_error: {result['max_abs_error']}")
        if result["failure_category"] is not None:
            lines.append(f"- failure_category: {result['failure_category']}")
        if result["failure_stage"] is not None:
            lines.append(f"- failure_stage: {result['failure_stage']}")
        if result["failure_reason"] is not None:
            lines.append(f"- failure_reason: {result['failure_reason']}")
        for stage_name, stage in result["stages"].items():
            detail = f" ({stage['detail']})" if stage["detail"] else ""
            lines.append(f"- {stage_name}: {stage['status']}{detail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _csv_rows(report: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in report["systems"]:
        rows.append(
            {
                "system_id": result["system_id"],
                "family": result["family"],
                "generated_state_count": result["generated_state_count"],
                "order": result["order"],
                "depth": result["depth"],
                "nonlinear": result["nonlinear"],
                "trig": result["trig"],
                "parse_success": result["parse_success"],
                "state_extraction_success": result["state_extraction_success"],
                "solve_success": result["solve_success"],
                "first_order_success": result["first_order_success"],
                "state_space_success": result["state_space_success"],
                "graph_success": result["graph_success"],
                "simulink_build_success": result["simulink_build_success"],
                "simulation_success": result["simulation_success"],
                "rmse": result["rmse"],
                "max_abs_error": result["max_abs_error"],
                "graph_node_count": result["graph_node_count"],
                "simulink_block_count": result["simulink_block_count"],
                "build_time_sec": result["build_time_sec"],
                "simulation_time_sec": result["simulation_time_sec"],
                "ode_simulation_time_sec": result["ode_simulation_time_sec"],
                "state_space_simulation_time_sec": result["state_space_simulation_time_sec"],
                "failure_category": result["failure_category"],
                "failure_stage": result["failure_stage"],
                "failure_reason": result["failure_reason"],
                "overall_pass": result["overall_pass"],
            }
        )
    return rows


def write_synthetic_benchmark_outputs(
    *,
    output_dir: str | Path = REPORTS_ROOT,
    data_dir: str | Path = DATA_ROOT,
    count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    seed: int = DEFAULT_SYNTHETIC_SEED,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
    progress_callback: Callable[[int, int, dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Generate the dataset, evaluate it, and write JSON/CSV/Markdown outputs."""
    systems = generate_synthetic_systems(count=count, seed=seed)
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    (data_path / "generated_systems.json").write_text(
        json.dumps([system.to_dict() for system in systems], indent=2),
        encoding="utf-8",
    )

    report = run_synthetic_benchmark(
        systems,
        count=count,
        seed=seed,
        tolerance=tolerance,
        run_simulink=run_simulink,
        progress_callback=progress_callback,
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_path / "benchmark.md").write_text(render_benchmark_markdown(report), encoding="utf-8")

    rows = _csv_rows(report)
    with (output_path / "benchmark.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    return report
