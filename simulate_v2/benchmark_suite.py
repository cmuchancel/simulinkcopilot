"""Comprehensive benchmark suite for the deterministic LaTeX compiler pipeline."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

import numpy as np

from backend_v2.builder import build_simulink_model
from backend_v2.extract_signals import extract_simulink_signals
from backend_v2.graph_to_simulink import graph_to_simulink_model
from backend_v2.simulate_simulink import prepare_workspace_variables, simulation_model_params
from backend_v2.validate_simulink import compare_simulink_results
from canonicalize_v2.first_order import build_first_order_system
from canonicalize_v2.linearity_check import analyze_first_order_linearity
from canonicalize_v2.solve_for_derivatives import solve_for_highest_derivatives
from canonicalize_v2.state_space import build_state_space_system
from ir_v2.equation_dict import equation_to_dict, equation_to_string
from ir_v2.graph_lowering import lower_first_order_system_graph
from ir_v2.graph_validate import validate_graph_dict
from latex_frontend_v2.symbols import DeterministicCompileError
from latex_frontend_v2.translator import translate_latex
from simulate_v2.compare import DEFAULT_TOLERANCE, compare_simulations
from simulate_v2.ode_sim import InputFunction, constant_inputs, simulate_ode_system
from simulate_v2.state_space_sim import simulate_state_space_system
from states_v2.extract_states import extract_states
from simulink_v2.engine import start_engine


@dataclass(frozen=True)
class BenchmarkCase:
    """Single benchmark system definition."""

    name: str
    category: str
    latex: str
    parameter_values: dict[str, float] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    input_function: InputFunction = field(default_factory=lambda: constant_inputs({}), repr=False, compare=False)
    classification_mode: str = "strict"
    symbol_config: Mapping[str, object] | None = None
    t_span: tuple[float, float] = (0.0, 10.0)
    sample_count: int = 300
    expected_linear: bool | None = True
    simulink_expected: bool = True
    expected_failure_stages: tuple[str, ...] = ()
    expected_failure_substring: str | None = None

    @property
    def expects_failure(self) -> bool:
        return bool(self.expected_failure_stages)


def sinusoidal_input(name: str, *, amplitude: float = 1.0, frequency: float = 1.0, bias: float = 0.0) -> InputFunction:
    """Return a deterministic sinusoidal input function."""

    def _input(time_value: float) -> dict[str, float]:
        return {name: bias + amplitude * math.sin(frequency * time_value)}

    return _input


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
        "comparison": _stage("skipped"),
        "simulink_build": _stage("skipped"),
        "simulink_compare": _stage("skipped"),
    }


def _time_grid(case: BenchmarkCase) -> np.ndarray:
    return np.linspace(case.t_span[0], case.t_span[1], case.sample_count)


def _input_signal_samples(case: BenchmarkCase, input_names: list[str], t_eval: np.ndarray) -> dict[str, dict[str, list[float]]]:
    return {
        name: {
            "time": [float(time_value) for time_value in t_eval.tolist()],
            "values": [float(case.input_function(float(time_value)).get(name, 0.0)) for time_value in t_eval],
        }
        for name in input_names
    }


def _constant_input_values(case: BenchmarkCase, input_names: list[str]) -> dict[str, float] | None:
    if not input_names:
        return {}
    start, stop = case.t_span
    sample_times = [float(start), float((start + stop) / 2.0), float(stop)]
    baseline = {
        name: float(case.input_function(sample_times[0]).get(name, 0.0))
        for name in input_names
    }
    for time_value in sample_times[1:]:
        sample = {
            name: float(case.input_function(time_value).get(name, 0.0))
            for name in input_names
        }
        if any(abs(sample[name] - baseline[name]) > 1e-12 for name in input_names):
            return None
    return baseline


BENCHMARK_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        name="basic_decay",
        category="Category 1 - Basic First-Order Systems",
        latex=r"\dot{x}=-ax",
        parameter_values={"a": 0.7},
        initial_conditions={"x": 1.0},
    ),
    BenchmarkCase(
        name="affine_first_order_input",
        category="Category 1 - Basic First-Order Systems",
        latex=r"\dot{x}=ax+bu",
        parameter_values={"a": -0.5, "b": 2.0},
        initial_conditions={"x": 0.0},
        input_function=constant_inputs({"u": 1.0}),
        classification_mode="configured",
        symbol_config={"u": "input", "b": "parameter"},
    ),
    BenchmarkCase(
        name="mass_spring",
        category="Category 2 - Second-Order Single-State Systems",
        latex=r"m\ddot{x}+kx=u",
        parameter_values={"m": 1.0, "k": 2.0},
        initial_conditions={"x": 0.0, "x_dot": 0.0},
        input_function=constant_inputs({"u": 1.0}),
    ),
    BenchmarkCase(
        name="mass_spring_damped",
        category="Category 2 - Second-Order Single-State Systems",
        latex=r"m\ddot{x}+c\dot{x}+kx=u",
        parameter_values={"m": 1.0, "c": 0.4, "k": 2.0},
        initial_conditions={"x": 0.0, "x_dot": 0.0},
        input_function=constant_inputs({"u": 1.0}),
    ),
    BenchmarkCase(
        name="third_order_single_state",
        category="Category 3 - Higher-Order Single-State Systems",
        latex=r"\frac{d^3 x}{dt^3}+a\ddot{x}+b\dot{x}+cx=u",
        parameter_values={"a": 1.2, "b": 0.5, "c": 1.0},
        initial_conditions={"x": 0.0, "x_dot": 0.0, "x_ddot": 0.0},
        input_function=constant_inputs({"u": 1.0}),
    ),
    BenchmarkCase(
        name="fourth_order_single_state",
        category="Category 3 - Higher-Order Single-State Systems",
        latex=r"\frac{d^4 x}{dt^4}+a\frac{d^3 x}{dt^3}+b\ddot{x}+c\dot{x}+dx=u",
        parameter_values={"a": 1.3, "b": 1.5, "c": 0.7, "d": 1.1},
        initial_conditions={"x": 0.0, "x_dot": 0.0, "x_ddot": 0.0, "x_d3": 0.0},
        input_function=constant_inputs({"u": 1.0}),
        t_span=(0.0, 6.0),
    ),
    BenchmarkCase(
        name="two_state_linear",
        category="Category 4 - Multi-State Linear Systems",
        latex="\\dot{x}=ax+by\n\\dot{y}=cx+dy",
        parameter_values={"a": -1.0, "b": 0.4, "c": -0.3, "d": -0.8},
        initial_conditions={"x": 1.0, "y": -0.5},
    ),
    BenchmarkCase(
        name="harmonic_pair",
        category="Category 4 - Multi-State Linear Systems",
        latex="\\dot{x_1}=x_2\n\\dot{x_2}=-x_1",
        initial_conditions={"x_1": 1.0, "x_2": 0.0},
        t_span=(0.0, 6.0),
    ),
    BenchmarkCase(
        name="two_mass_undamped",
        category="Category 5 - Coupled Second-Order Systems",
        latex="m_1\\ddot{x_1}=-k(x_1-x_2)\n"
        "m_2\\ddot{x_2}=k(x_1-x_2)",
        parameter_values={"m_1": 1.0, "m_2": 1.2, "k": 2.0},
        initial_conditions={"x_1": 0.4, "x_1_dot": 0.0, "x_2": 0.0, "x_2_dot": 0.0},
        t_span=(0.0, 6.0),
    ),
    BenchmarkCase(
        name="two_mass_damped",
        category="Category 5 - Coupled Second-Order Systems",
        latex="m_1\\ddot{x_1}=-k(x_1-x_2)-c(\\dot{x_1}-\\dot{x_2})\n"
        "m_2\\ddot{x_2}=k(x_1-x_2)+c(\\dot{x_1}-\\dot{x_2})",
        parameter_values={"m_1": 1.0, "m_2": 1.3, "k": 2.0, "c": 0.25},
        initial_conditions={"x_1": 0.4, "x_1_dot": 0.0, "x_2": 0.0, "x_2_dot": 0.0},
        t_span=(0.0, 6.0),
    ),
    BenchmarkCase(
        name="three_mass_chain",
        category="Category 6 - Multi-Mass Systems (Scaling)",
        latex="m_1\\ddot{x_1}=-k(x_1-x_2)\n"
        "m_2\\ddot{x_2}=k(x_1-x_2)-k(x_2-x_3)\n"
        "m_3\\ddot{x_3}=k(x_2-x_3)",
        parameter_values={"m_1": 1.0, "m_2": 1.1, "m_3": 0.9, "k": 1.6},
        initial_conditions={
            "x_1": 0.3,
            "x_1_dot": 0.0,
            "x_2": 0.0,
            "x_2_dot": 0.0,
            "x_3": -0.2,
            "x_3_dot": 0.0,
        },
        t_span=(0.0, 6.0),
    ),
    BenchmarkCase(
        name="driven_mass_spring",
        category="Category 7 - Driven Systems",
        latex=r"m\ddot{x}+c\dot{x}+kx=u(t)",
        parameter_values={"m": 1.0, "c": 0.2, "k": 2.0},
        initial_conditions={"x": 0.0, "x_dot": 0.0},
        input_function=sinusoidal_input("u", amplitude=0.05, frequency=0.3),
        t_span=(0.0, 4.0),
        sample_count=320,
    ),
    BenchmarkCase(
        name="mixed_first_second",
        category="Category 8 - Mixed First + Second Order",
        latex="\\dot{x}=v\nm\\dot{v}+kv=u",
        parameter_values={"m": 1.0, "k": 0.8},
        initial_conditions={"x": 0.0, "v": 0.0},
        input_function=constant_inputs({"u": 1.0}),
    ),
    BenchmarkCase(
        name="nonlinear_square",
        category="Category 9 - Nonlinear Polynomial Systems",
        latex=r"\dot{x}=x^2",
        initial_conditions={"x": 0.1},
        expected_linear=False,
        t_span=(0.0, 1.0),
        sample_count=240,
    ),
    BenchmarkCase(
        name="nonlinear_affine_polynomial",
        category="Category 9 - Nonlinear Polynomial Systems",
        latex=r"\dot{x}=ax^2+bx+c",
        parameter_values={"a": -0.5, "b": -0.2, "c": 0.1},
        initial_conditions={"x": 0.2},
        classification_mode="configured",
        symbol_config={"c": "parameter"},
        expected_linear=False,
        t_span=(0.0, 4.0),
    ),
    BenchmarkCase(
        name="nonlinear_coupled",
        category="Category 10 - Nonlinear Coupled Systems",
        latex="\\dot{x}=y^2\n\\dot{y}=-x^3",
        initial_conditions={"x": 0.3, "y": 0.1},
        expected_linear=False,
        t_span=(0.0, 4.0),
    ),
    BenchmarkCase(
        name="nonlinear_pendulum",
        category="Category 11 - Nonlinear Physical Systems",
        latex=r"\ddot{\theta}+\frac{g}{l}\sin(\theta)=0",
        parameter_values={"g": 9.81, "l": 1.0},
        initial_conditions={"q": 0.3, "q_dot": 0.0},
        expected_linear=False,
        t_span=(0.0, 4.0),
        sample_count=320,
    ),
    BenchmarkCase(
        name="fail_dae",
        category="Category 12 - Systems That SHOULD FAIL",
        latex="x+y=1\n\\dot{x}=y",
        expected_linear=None,
        simulink_expected=False,
        expected_failure_stages=("solve",),
        expected_failure_substring="algebraic/DAE-like",
    ),
    BenchmarkCase(
        name="fail_implicit_derivative",
        category="Category 12 - Systems That SHOULD FAIL",
        latex=r"\dot{x}+\sin(\dot{x})=u",
        expected_linear=None,
        simulink_expected=False,
        expected_failure_stages=("solve",),
        expected_failure_substring="implicit nonlinear derivative coupling",
    ),
    BenchmarkCase(
        name="fail_underdetermined",
        category="Category 12 - Systems That SHOULD FAIL",
        latex=r"\dot{x}+y=u",
        expected_linear=None,
        simulink_expected=False,
        classification_mode="configured",
        symbol_config={"u": "input"},
        expected_failure_stages=("state_extraction",),
    ),
    BenchmarkCase(
        name="fail_unsupported_syntax",
        category="Category 12 - Systems That SHOULD FAIL",
        latex=r"\int x dt",
        expected_linear=None,
        simulink_expected=False,
        expected_failure_stages=("parse",),
        expected_failure_substring="Unsupported",
    ),
)


def _check_expected_failure(case: BenchmarkCase, stage_name: str, error_text: str) -> bool:
    if stage_name not in case.expected_failure_stages:
        return False
    if case.expected_failure_substring is None:
        return True
    return case.expected_failure_substring.lower() in error_text.lower()


def _finalize_case(
    case: BenchmarkCase,
    *,
    stages: dict[str, dict[str, object]],
    metrics: dict[str, object],
    failure_stage: str | None = None,
    failure_reason: str | None = None,
    linearity: dict[str, object] | None = None,
    comparison: dict[str, object] | None = None,
    simulink_validation: dict[str, object] | None = None,
    equations: list[object] | None = None,
) -> dict[str, object]:
    serialized_linearity = None
    if linearity is not None:
        serialized_linearity = {
            "is_linear": linearity["is_linear"],
            "A": str(linearity["A"]),
            "B": str(linearity["B"]),
            "offset": str(linearity["offset"]),
            "offending_entries": linearity["offending_entries"],
        }

    if case.expects_failure:
        overall_pass = (
            failure_stage is not None
            and failure_reason is not None
            and _check_expected_failure(case, failure_stage, failure_reason)
        )
    else:
        comparison_stage_ok = stages["comparison"]["status"] in {"passed", "skipped"}
        simulink_stage_ok = stages["simulink_compare"]["status"] in {"passed", "skipped"}
        overall_pass = all(
            stages[name]["status"] == "passed"
            for name in [
                "parse",
                "state_extraction",
                "solve",
                "first_order",
                "graph_lowering",
                "graph_validation",
                "ode_simulation",
            ]
        ) and comparison_stage_ok and simulink_stage_ok

    return {
        "name": case.name,
        "category": case.category,
        "latex": case.latex,
        "expected_linear": case.expected_linear,
        "stages": stages,
        "metrics": metrics,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "linearity": serialized_linearity,
        "comparison": comparison,
        "simulink_validation": simulink_validation,
        "equations": [equation_to_string(eq) for eq in equations] if equations is not None else None,
        "overall_pass": overall_pass,
    }


def run_full_system_benchmark(
    *,
    selected_cases: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
) -> dict[str, object]:
    """Run the full benchmark suite and return a structured report."""
    selected = set(selected_cases or [case.name for case in BENCHMARK_CASES])
    cases = [case for case in BENCHMARK_CASES if case.name in selected]

    eng = None
    engine_error: str | None = None
    if run_simulink and any(case.simulink_expected and not case.expects_failure for case in cases):
        try:
            eng = start_engine(retries=1, retry_delay_seconds=1.0)
        except Exception as exc:  # pragma: no cover - environment dependent
            engine_error = str(exc)

    results: list[dict[str, object]] = []
    try:
        for case in cases:
            stages = _default_stages()
            metrics: dict[str, object] = {
                "state_count": None,
                "graph_nodes": None,
                "simulink_blocks": None,
                "ode_simulation_time_sec": None,
                "state_space_simulation_time_sec": None,
                "simulink_build_time_sec": None,
                "simulink_simulation_time_sec": None,
            }
            failure_stage = None
            failure_reason = None
            equations = None
            linearity = None
            comparison = None
            simulink_validation = None

            try:
                equations = translate_latex(case.latex)
                stages["parse"] = _stage("passed")
            except Exception as exc:
                failure_stage = "parse"
                failure_reason = str(exc)
                stages["parse"] = _stage(
                    "expected_failure" if _check_expected_failure(case, "parse", str(exc)) else "failed",
                    str(exc),
                )
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                    )
                )
                continue

            try:
                extraction = extract_states(
                    equations,
                    mode=case.classification_mode,
                    symbol_config=case.symbol_config,
                )
                stages["state_extraction"] = _stage("passed")
                metrics["state_count"] = len(extraction.states)
            except Exception as exc:
                failure_stage = "state_extraction"
                failure_reason = str(exc)
                stages["state_extraction"] = _stage(
                    "expected_failure"
                    if _check_expected_failure(case, "state_extraction", str(exc))
                    else "failed",
                    str(exc),
                )
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                    )
                )
                continue

            try:
                solved = solve_for_highest_derivatives(equations)
                stages["solve"] = _stage("passed")
            except Exception as exc:
                failure_stage = "solve"
                failure_reason = str(exc)
                stages["solve"] = _stage(
                    "expected_failure" if _check_expected_failure(case, "solve", str(exc)) else "failed",
                    str(exc),
                )
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                    )
                )
                continue

            try:
                first_order = build_first_order_system(equations, extraction=extraction, solved_derivatives=solved)
                stages["first_order"] = _stage("passed")
            except Exception as exc:
                failure_stage = "first_order"
                failure_reason = str(exc)
                stages["first_order"] = _stage("failed", str(exc))
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                    )
                )
                continue

            try:
                linearity = analyze_first_order_linearity(first_order)
                if linearity["is_linear"]:
                    state_space = build_state_space_system(first_order)
                    stages["state_space"] = _stage("passed")
                else:
                    state_space = None
                    stages["state_space"] = _stage("skipped", "nonlinear explicit system")
            except Exception as exc:
                state_space = None
                failure_stage = "state_space"
                failure_reason = str(exc)
                stages["state_space"] = _stage("failed", str(exc))
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                        linearity=linearity,
                    )
                )
                continue

            try:
                graph = lower_first_order_system_graph(first_order, name=case.name)
                metrics["graph_nodes"] = len(graph["nodes"])
                stages["graph_lowering"] = _stage("passed")
            except Exception as exc:
                failure_stage = "graph_lowering"
                failure_reason = str(exc)
                stages["graph_lowering"] = _stage("failed", str(exc))
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                        linearity=linearity,
                    )
                )
                continue

            try:
                graph = validate_graph_dict(graph)
                stages["graph_validation"] = _stage("passed")
            except Exception as exc:
                failure_stage = "graph_validation"
                failure_reason = str(exc)
                stages["graph_validation"] = _stage("failed", str(exc))
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                        linearity=linearity,
                    )
                )
                continue

            t_eval = _time_grid(case)
            try:
                ode_start = time.perf_counter()
                ode_result = simulate_ode_system(
                    first_order,
                    parameter_values=case.parameter_values,
                    initial_conditions=case.initial_conditions,
                    input_function=case.input_function,
                    t_span=case.t_span,
                    t_eval=t_eval,
                )
                metrics["ode_simulation_time_sec"] = time.perf_counter() - ode_start
                stages["ode_simulation"] = _stage("passed")
            except Exception as exc:
                failure_stage = "ode_simulation"
                failure_reason = str(exc)
                stages["ode_simulation"] = _stage("failed", str(exc))
                results.append(
                    _finalize_case(
                        case,
                        stages=stages,
                        metrics=metrics,
                        failure_stage=failure_stage,
                        failure_reason=failure_reason,
                        equations=equations,
                        linearity=linearity,
                    )
                )
                continue

            if state_space is not None:
                try:
                    state_space_start = time.perf_counter()
                    state_space_result = simulate_state_space_system(
                        state_space,
                        parameter_values=case.parameter_values,
                        initial_conditions=case.initial_conditions,
                        input_function=case.input_function,
                        t_span=case.t_span,
                        t_eval=t_eval,
                    )
                    metrics["state_space_simulation_time_sec"] = time.perf_counter() - state_space_start
                    comparison = compare_simulations(ode_result, state_space_result, tolerance=tolerance)
                    if comparison["passes"]:
                        stages["comparison"] = _stage(
                            "passed",
                            f"rmse={comparison['rmse']:.3e}, max={comparison['max_abs_error']:.3e}",
                        )
                    else:
                        stages["comparison"] = _stage(
                            "failed",
                            f"rmse={comparison['rmse']:.3e}, max={comparison['max_abs_error']:.3e}",
                        )
                except Exception as exc:
                    failure_stage = "comparison"
                    failure_reason = str(exc)
                    stages["comparison"] = _stage("failed", str(exc))
                    results.append(
                        _finalize_case(
                            case,
                            stages=stages,
                            metrics=metrics,
                            failure_stage=failure_stage,
                            failure_reason=failure_reason,
                            equations=equations,
                            linearity=linearity,
                            comparison=comparison,
                        )
                    )
                    continue
            else:
                state_space_result = None
                stages["comparison"] = _stage("skipped", "state-space comparison not available")

            if case.simulink_expected:
                if not run_simulink:
                    stages["simulink_build"] = _stage("skipped", "Simulink benchmark disabled")
                    stages["simulink_compare"] = _stage("skipped", "Simulink benchmark disabled")
                elif engine_error is not None or eng is None:
                    failure_stage = "simulink_build"
                    failure_reason = engine_error or "MATLAB engine unavailable"
                    stages["simulink_build"] = _stage("failed", failure_reason)
                    stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                else:
                    try:
                        input_names = list(first_order["inputs"])  # type: ignore[index]
                        input_values = _constant_input_values(case, input_names)
                        input_signals = None if input_values is not None else _input_signal_samples(case, input_names, t_eval)
                        model_params = simulation_model_params(t_span=case.t_span, t_eval=t_eval)
                        model = graph_to_simulink_model(
                            graph,
                            name=f"{case.name}_simulink",
                            state_names=list(first_order["states"]),  # type: ignore[index]
                            parameter_values=case.parameter_values,
                            input_values=input_values,
                            input_signals=input_signals,
                            initial_conditions=case.initial_conditions,
                            model_params=model_params,
                        )
                        metrics["simulink_blocks"] = len(model["blocks"])
                        build_start = time.perf_counter()
                        build_info = build_simulink_model(
                            eng,
                            model,
                            output_dir=Path("generated_models") / "benchmark_models",
                        )
                        prepare_workspace_variables(eng, model)
                        metrics["simulink_build_time_sec"] = time.perf_counter() - build_start
                        stages["simulink_build"] = _stage("passed", build_info["model_file"])

                        sim_start = time.perf_counter()
                        sim_output = eng.sim(build_info["model_name"], "ReturnWorkspaceOutputs", "on", nargout=1)
                        sim_result = extract_simulink_signals(
                            eng,
                            sim_output,
                            output_names=[entry["name"] for entry in model["outputs"]],
                        )
                        metrics["simulink_simulation_time_sec"] = time.perf_counter() - sim_start
                        simulink_validation = compare_simulink_results(
                            sim_result,
                            ode_result,
                            state_space_result,
                            tolerance=tolerance,
                        )
                        if simulink_validation["passes"]:
                            stages["simulink_compare"] = _stage(
                                "passed",
                                f"rmse={simulink_validation['vs_ode']['rmse']:.3e}, "
                                f"max={simulink_validation['vs_ode']['max_abs_error']:.3e}",
                            )
                        else:
                            stages["simulink_compare"] = _stage(
                                "failed",
                                f"rmse={simulink_validation['vs_ode']['rmse']:.3e}, "
                                f"max={simulink_validation['vs_ode']['max_abs_error']:.3e}",
                            )
                    except Exception as exc:
                        failure_stage = "simulink_build" if stages["simulink_build"]["status"] != "passed" else "simulink_compare"
                        failure_reason = str(exc)
                        if stages["simulink_build"]["status"] != "passed":
                            stages["simulink_build"] = _stage("failed", str(exc))
                            stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                        else:
                            stages["simulink_compare"] = _stage("failed", str(exc))

            results.append(
                _finalize_case(
                    case,
                    stages=stages,
                    metrics=metrics,
                    failure_stage=failure_stage,
                    failure_reason=failure_reason,
                    equations=equations,
                    linearity=linearity,
                    comparison=comparison,
                    simulink_validation=simulink_validation,
                )
            )
    finally:
        if eng is not None:
            eng.quit()

    passed = sum(1 for result in results if result["overall_pass"])
    report = {
        "generated_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "tolerance": tolerance,
        "categories": sorted({case.category for case in cases}),
        "cases": results,
    }
    return report


def render_full_system_benchmark_markdown(report: dict[str, object]) -> str:
    """Render the benchmark report as Markdown."""
    lines = [
        "# Full System Benchmark",
        "",
        f"- cases run: {report['generated_cases']}",
        f"- passed: {report['passed_cases']}",
        f"- failed: {report['failed_cases']}",
        f"- tolerance: {report['tolerance']}",
        "",
    ]

    by_category: dict[str, list[dict[str, object]]] = {}
    for case in report["cases"]:
        by_category.setdefault(case["category"], []).append(case)

    for category in sorted(by_category):
        lines.append(f"## {category}")
        for case in by_category[category]:
            lines.append(f"### {case['name']}")
            lines.append(f"- overall_pass: {case['overall_pass']}")
            lines.append(f"- latex: `{case['latex']}`")
            if case["failure_stage"] is not None:
                lines.append(f"- failure_stage: {case['failure_stage']}")
            if case["failure_reason"] is not None:
                lines.append(f"- failure_reason: {case['failure_reason']}")
            metrics = case["metrics"]
            lines.append(f"- state_count: {metrics['state_count']}")
            lines.append(f"- graph_nodes: {metrics['graph_nodes']}")
            lines.append(f"- simulink_blocks: {metrics['simulink_blocks']}")
            lines.append(f"- ode_simulation_time_sec: {metrics['ode_simulation_time_sec']}")
            lines.append(f"- state_space_simulation_time_sec: {metrics['state_space_simulation_time_sec']}")
            lines.append(f"- simulink_build_time_sec: {metrics['simulink_build_time_sec']}")
            lines.append(f"- simulink_simulation_time_sec: {metrics['simulink_simulation_time_sec']}")
            for stage_name, stage in case["stages"].items():
                detail = f" ({stage['detail']})" if stage["detail"] else ""
                lines.append(f"- {stage_name}: {stage['status']}{detail}")
            if case["comparison"] is not None:
                lines.append(
                    f"- comparison_metrics: rmse={case['comparison']['rmse']:.3e}, "
                    f"max={case['comparison']['max_abs_error']:.3e}"
                )
            if case["simulink_validation"] is not None:
                lines.append(
                    f"- simulink_metrics: rmse={case['simulink_validation']['vs_ode']['rmse']:.3e}, "
                    f"max={case['simulink_validation']['vs_ode']['max_abs_error']:.3e}"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_full_system_benchmark_reports(
    output_dir: str | Path = "reports",
    *,
    selected_cases: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
) -> dict[str, object]:
    """Run the full benchmark suite and write JSON/Markdown reports."""
    report = run_full_system_benchmark(
        selected_cases=selected_cases,
        tolerance=tolerance,
        run_simulink=run_simulink,
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "full_system_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_path / "full_system_benchmark.md").write_text(
        render_full_system_benchmark_markdown(report),
        encoding="utf-8",
    )
    return report
