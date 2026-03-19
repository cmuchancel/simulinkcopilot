"""Execution and reporting for the extended SimuCompileBench suite."""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from backend.builder import build_simulink_model
from backend.extract_signals import extract_simulink_signals
from backend.graph_to_simulink import graph_to_simulink_model
from backend.simulate_simulink import prepare_workspace_variables, simulation_model_params
from backend.validate_simulink import compare_simulink_results
from canonicalize.first_order import build_first_order_system
from canonicalize.linearity_check import analyze_first_order_linearity
from canonicalize.solve_for_derivatives import solve_for_highest_derivatives
from canonicalize.state_space import build_state_space_system
from ir.equation_dict import equation_to_string
from ir.graph_lowering import lower_first_order_system_graph
from ir.graph_validate import validate_graph_dict
from latex_frontend.translator import translate_latex
from simulate.compare import DEFAULT_TOLERANCE, compare_simulations
from simulate.ode_sim import constant_inputs, simulate_ode_system
from simulate.state_space_sim import simulate_state_space_system
from states.extract_states import extract_states
from simulink.engine import start_engine

from .catalog import build_simucompilebench_specs
from .models import BenchmarkSystemSpec


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


def _mean(values: list[float | None]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return float(sum(filtered) / len(filtered))


def _validate_numeric_result(name: str, result: dict[str, object]) -> None:
    states = np.asarray(result["states"], dtype=float)
    if not np.isfinite(states).all():
        raise RuntimeError(f"{name} produced non-finite state values.")


def _failure_category(failure_stage: str | None, failure_reason: str | None) -> str | None:
    if failure_stage is None:
        return None
    reason = (failure_reason or "").lower()
    if failure_stage == "parse":
        return "parse_failure"
    if failure_stage in {"graph_lowering", "graph_validation"}:
        return "graph_invalid"
    if failure_stage in {"ode_simulation", "state_space_simulation", "simulink_simulation", "simulink_compare"}:
        if any(token in reason for token in ("non-finite", "nan", "inf", "required step size", "diverg", "overflow")):
            return "numerical_instability"
        return "simulation_failure"
    if failure_stage in {"solve", "state_extraction", "first_order", "state_space"}:
        return "symbolic_failure"
    if failure_stage == "simulink_build":
        return "simulink_failure"
    return "other_failure"


def _inject_graph_fault(graph: dict[str, Any], fault_name: str | None) -> dict[str, Any]:
    if fault_name is None:
        return graph
    broken = json.loads(json.dumps(graph))
    if fault_name == "drop_node":
        nodes = list(broken["nodes"])
        edges = list(broken["edges"])
        if len(nodes) < 2 or not edges:
            return broken
        doomed_id = str(nodes[-1]["id"])
        broken["nodes"] = [node for node in nodes if str(node["id"]) != doomed_id]
        if edges:
            edges[0]["source"] = doomed_id
        broken["edges"] = edges
        return broken
    raise RuntimeError(f"Unsupported graph fault injection '{fault_name}'.")


def _match_expected_failure(spec: BenchmarkSystemSpec, failure_stage: str | None, failure_reason: str | None) -> bool:
    if spec.expected_failure_stage is None:
        return False
    if failure_stage != spec.expected_failure_stage:
        return False
    if spec.expected_failure_substring is None:
        return True
    return spec.expected_failure_substring in (failure_reason or "")


def _robustness_score(
    spec: BenchmarkSystemSpec,
    first_order: dict[str, object],
    *,
    state_space: dict[str, object] | None,
    tolerance: float,
) -> float | None:
    state_names = list(first_order["states"])  # type: ignore[index]
    if not state_names:
        return None
    scales = (0.5, 1.5, 2.0)
    pass_count = 0
    input_function = constant_inputs(spec.input_values)
    t_eval = np.linspace(spec.t_span[0], spec.t_span[1], max(80, min(spec.sample_count, 180)))
    for scale in scales:
        initial_conditions: dict[str, float] = {}
        for index, state_name in enumerate(state_names, start=1):
            baseline = float(spec.initial_conditions.get(state_name, 0.0))
            if abs(baseline) > 1e-12:
                initial_conditions[state_name] = baseline * scale
            else:
                initial_conditions[state_name] = 0.01 * scale * index
        try:
            ode_result = simulate_ode_system(
                first_order,
                parameter_values=spec.parameter_values,
                initial_conditions=initial_conditions,
                input_function=input_function,
                t_span=spec.t_span,
                t_eval=t_eval,
            )
            _validate_numeric_result("robustness ODE simulation", ode_result)
            if state_space is not None:
                state_space_result = simulate_state_space_system(
                    state_space,
                    parameter_values=spec.parameter_values,
                    initial_conditions=initial_conditions,
                    input_function=input_function,
                    t_span=spec.t_span,
                    t_eval=t_eval,
                )
                _validate_numeric_result("robustness state-space simulation", state_space_result)
                comparison = compare_simulations(ode_result, state_space_result, tolerance=tolerance)
                if not comparison["passes"]:
                    continue
            pass_count += 1
        except Exception:
            continue
    return float(pass_count / len(scales))


def _result_row(
    spec: BenchmarkSystemSpec,
    *,
    stages: dict[str, dict[str, object]],
    failure_stage: str | None,
    failure_reason: str | None,
    normalized_equations: list[str] | None,
    extracted_state_count: int | None,
    graph_node_count: int | None,
    simulink_block_count: int | None,
    state_space_available: bool,
    ode_simulation_time_sec: float | None,
    state_space_simulation_time_sec: float | None,
    simulink_build_time_sec: float | None,
    simulink_simulation_time_sec: float | None,
    state_space_rmse: float | None,
    state_space_max_abs_error: float | None,
    simulink_rmse: float | None,
    simulink_max_abs_error: float | None,
    robustness_score: float | None,
) -> dict[str, object]:
    expected_failure_observed = _match_expected_failure(spec, failure_stage, failure_reason)
    failure_category = _failure_category(failure_stage, failure_reason)
    if spec.expected_failure_category is not None and expected_failure_observed:
        failure_category = spec.expected_failure_category

    if spec.expects_failure:
        overall_pass = expected_failure_observed
        benchmark_result = "expected_failure_observed" if expected_failure_observed else "missed_expected_failure"
    else:
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
        benchmark_result = "pass" if overall_pass else "unexpected_failure"

    primary_rmse = simulink_rmse if simulink_rmse is not None else state_space_rmse
    primary_max = simulink_max_abs_error if simulink_max_abs_error is not None else state_space_max_abs_error
    return {
        "system_id": spec.system_id,
        "tier": spec.tier,
        "family": spec.family,
        "latex": spec.latex,
        "tags": list(spec.tags),
        "generated_state_count": spec.generated_state_count,
        "order": spec.max_order,
        "depth": spec.depth,
        "nonlinear": spec.nonlinear,
        "trig": spec.includes_trig,
        "expected_failure": spec.expects_failure,
        "state_space_available": state_space_available,
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
        "robustness_score": robustness_score,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "failure_category": failure_category,
        "benchmark_result": benchmark_result,
        "overall_pass": overall_pass,
        "stages": stages,
    }


def run_extended_benchmark(
    specs: list[BenchmarkSystemSpec] | None = None,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
    progress_callback: Callable[[int, int, dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Run the additive SimuCompileBench systems beyond the locked legacy suite."""
    specs = list(specs or [spec for spec in build_simucompilebench_specs(include_legacy=False)])
    total = len(specs)

    eng = None
    engine_error: str | None = None
    if run_simulink:
        try:
            eng = start_engine(retries=1, retry_delay_seconds=1.0)
        except Exception as exc:  # pragma: no cover - environment dependent
            engine_error = str(exc)

    results: list[dict[str, object]] = []
    try:
        for index, spec in enumerate(specs, start=1):
            stages = _default_stages()
            failure_stage = None
            failure_reason = None
            normalized_equations = None
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
            robustness_score = None
            state_space_available = False
            first_order = None
            state_space = None
            ode_result = None
            state_space_result = None

            try:
                equations = translate_latex(spec.latex)
                normalized_equations = [equation_to_string(item) for item in equations]
                stages["parse"] = _stage("passed")

                extraction = extract_states(
                    equations,
                    mode=spec.classification_mode,
                    symbol_config=dict(spec.symbol_config or {}),
                )
                extracted_state_count = len(extraction.states)
                stages["state_extraction"] = _stage("passed")

                solved = solve_for_highest_derivatives(equations)
                stages["solve"] = _stage("passed")

                first_order = build_first_order_system(equations, extraction=extraction, solved_derivatives=solved)
                stages["first_order"] = _stage("passed")

                try:
                    linearity = analyze_first_order_linearity(first_order)
                    if linearity["is_linear"]:
                        state_space = build_state_space_system(first_order)
                        state_space_available = True
                        stages["state_space"] = _stage("passed")
                    else:
                        stages["state_space"] = _stage("skipped", "nonlinear explicit system")
                except Exception as exc:
                    stages["state_space"] = _stage("failed", str(exc))
                    failure_stage = failure_stage or "state_space"
                    failure_reason = failure_reason or str(exc)

                graph = lower_first_order_system_graph(first_order, name=spec.system_id)
                stages["graph_lowering"] = _stage("passed")
                graph_node_count = len(graph["nodes"])

                graph = _inject_graph_fault(graph, spec.graph_fault)
                graph = validate_graph_dict(graph)
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
                else:
                    stages["state_space_simulation"] = _stage("skipped", "state-space unavailable")
                    stages["state_space_compare"] = _stage("skipped", "state-space unavailable")

                if run_simulink and spec.simulink_expected and not spec.expects_failure:
                    if engine_error is not None or eng is None:
                        stages["simulink_build"] = _stage("failed", engine_error or "MATLAB engine unavailable")
                        stages["simulink_simulation"] = _stage("skipped", "Simulink build failed")
                        stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                        failure_stage = failure_stage or "simulink_build"
                        failure_reason = failure_reason or engine_error or "MATLAB engine unavailable"
                    else:
                        model_name = None
                        try:
                            model = graph_to_simulink_model(
                                graph,
                                name=f"{spec.system_id}_simulink",
                                state_names=list(first_order["states"]),  # type: ignore[index]
                                parameter_values=spec.parameter_values,
                                input_values=spec.input_values,
                                initial_conditions=spec.initial_conditions,
                                model_params=simulation_model_params(t_span=spec.t_span, t_eval=t_eval),
                            )
                            simulink_block_count = len(model["blocks"])
                            build_start = time.perf_counter()
                            build_info = build_simulink_model(
                                eng,
                                model,
                                output_dir=Path("generated_models") / "simucompilebench_models",
                            )
                            simulink_build_time_sec = time.perf_counter() - build_start
                            model_name = str(build_info["model_name"])
                            stages["simulink_build"] = _stage("passed", str(build_info["model_file"]))

                            prepare_workspace_variables(eng, model)
                            sim_start = time.perf_counter()
                            sim_output = eng.sim(model_name, "ReturnWorkspaceOutputs", "on", nargout=1)
                            sim_result = extract_simulink_signals(
                                eng,
                                sim_output,
                                output_names=[entry["name"] for entry in model["outputs"]],
                            )
                            simulink_simulation_time_sec = time.perf_counter() - sim_start
                            _validate_numeric_result("Simulink simulation", sim_result)
                            stages["simulink_simulation"] = _stage("passed")

                            simulink_validation = compare_simulink_results(
                                sim_result,
                                ode_result,
                                state_space_result,
                                tolerance=tolerance,
                            )
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
                        finally:
                            if eng is not None and model_name is not None:
                                try:
                                    eng.close_system(model_name, 0, nargout=0)
                                except Exception:  # pragma: no cover - cleanup best effort
                                    pass
                else:
                    skip_reason = "Simulink disabled" if not run_simulink else "Simulink not required for this case"
                    stages["simulink_build"] = _stage("skipped", skip_reason)
                    stages["simulink_simulation"] = _stage("skipped", skip_reason)
                    stages["simulink_compare"] = _stage("skipped", skip_reason)

                if not spec.expects_failure and first_order is not None and stages["ode_simulation"]["status"] == "passed":
                    robustness_score = _robustness_score(spec, first_order, state_space=state_space, tolerance=tolerance)
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
                elif stages["state_space_simulation"]["status"] not in {"passed", "skipped"}:
                    failure_stage = failure_stage or "state_space_simulation"
                    stages["state_space_simulation"] = _stage("failed", str(exc))
                elif stages["simulink_build"]["status"] not in {"passed", "skipped"}:
                    failure_stage = failure_stage or "simulink_build"
                    stages["simulink_build"] = _stage("failed", str(exc))
                elif stages["simulink_simulation"]["status"] not in {"passed", "skipped"}:
                    failure_stage = failure_stage or "simulink_simulation"
                    stages["simulink_simulation"] = _stage("failed", str(exc))
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
                state_space_available=state_space_available,
                ode_simulation_time_sec=ode_simulation_time_sec,
                state_space_simulation_time_sec=state_space_simulation_time_sec,
                simulink_build_time_sec=simulink_build_time_sec,
                simulink_simulation_time_sec=simulink_simulation_time_sec,
                state_space_rmse=state_space_rmse,
                state_space_max_abs_error=state_space_max_abs_error,
                simulink_rmse=simulink_rmse,
                simulink_max_abs_error=simulink_max_abs_error,
                robustness_score=robustness_score,
            )
            results.append(result)
            if progress_callback is not None:
                progress_callback(index, total, result)
    finally:
        if eng is not None:
            eng.quit()

    return _aggregate_report(results, tolerance=tolerance, report_name="SimuCompileBench Extended")


def convert_legacy_results(
    legacy_report: dict[str, Any],
    legacy_specs: list[BenchmarkSystemSpec],
) -> list[dict[str, object]]:
    """Normalize the locked legacy synthetic results into the SimuCompileBench schema."""
    spec_by_id = {spec.system_id: spec for spec in legacy_specs}
    converted: list[dict[str, object]] = []
    for item in legacy_report["systems"]:
        spec = spec_by_id[str(item["system_id"])]
        converted.append(
            {
                "system_id": spec.system_id,
                "tier": spec.tier,
                "family": spec.family,
                "latex": spec.latex,
                "tags": list(spec.tags),
                "generated_state_count": spec.generated_state_count,
                "order": spec.max_order,
                "depth": spec.depth,
                "nonlinear": spec.nonlinear,
                "trig": spec.includes_trig,
                "expected_failure": False,
                "state_space_available": bool(item["state_space_success"]),
                "normalized_equations": item.get("normalized_equations"),
                "extracted_state_count": item.get("extracted_state_count"),
                "graph_node_count": item.get("graph_node_count"),
                "simulink_block_count": item.get("simulink_block_count"),
                "ode_simulation_time_sec": item.get("ode_simulation_time_sec"),
                "state_space_simulation_time_sec": item.get("state_space_simulation_time_sec"),
                "build_time_sec": item.get("build_time_sec"),
                "simulation_time_sec": item.get("simulation_time_sec"),
                "rmse": item.get("rmse"),
                "max_abs_error": item.get("max_abs_error"),
                "state_space_rmse": item.get("state_space_rmse"),
                "state_space_max_abs_error": item.get("state_space_max_abs_error"),
                "simulink_rmse": item.get("simulink_rmse"),
                "simulink_max_abs_error": item.get("simulink_max_abs_error"),
                "robustness_score": None,
                "failure_stage": item.get("failure_stage"),
                "failure_reason": item.get("failure_reason"),
                "failure_category": _failure_category(item.get("failure_stage"), item.get("failure_reason")),
                "benchmark_result": "pass" if item["overall_pass"] else "unexpected_failure",
                "overall_pass": bool(item["overall_pass"]),
                "stages": item["stages"],
            }
        )
    return converted


def _aggregate_report(results: list[dict[str, object]], *, tolerance: float, report_name: str) -> dict[str, object]:
    passed = sum(1 for item in results if item["overall_pass"])
    failed = len(results) - passed
    failure_categories: dict[str, int] = {}
    tier_summary: dict[str, dict[str, object]] = {}
    family_summary: dict[str, dict[str, object]] = {}
    state_count_summary: dict[str, dict[str, object]] = {}

    for item in results:
        category = item["failure_category"]
        if category is not None:
            failure_categories[str(category)] = failure_categories.get(str(category), 0) + 1

        for bucket, key in ((tier_summary, "tier"), (family_summary, "family"), (state_count_summary, "generated_state_count")):
            bucket_key = str(item[key])
            entry = bucket.setdefault(bucket_key, {"systems": 0, "passed": 0})
            entry["systems"] += 1
            if item["overall_pass"]:
                entry["passed"] += 1

    for bucket in (tier_summary, family_summary, state_count_summary):
        for entry in bucket.values():
            entry["success_rate"] = float(entry["passed"] / entry["systems"])

    complexity_by_state_count: dict[str, dict[str, object]] = {}
    for count_value in sorted({int(item["generated_state_count"]) for item in results}):
        subset = [item for item in results if int(item["generated_state_count"]) == count_value]
        complexity_by_state_count[str(count_value)] = {
            "systems": len(subset),
            "average_graph_nodes": _mean([item["graph_node_count"] for item in subset]),
            "average_simulink_blocks": _mean([item["simulink_block_count"] for item in subset]),
            "average_build_time_sec": _mean([item["build_time_sec"] for item in subset]),
            "average_simulation_time_sec": _mean([item["simulation_time_sec"] for item in subset]),
        }

    rmse_values = [float(item["rmse"]) for item in results if item["rmse"] is not None]
    max_error_values = [float(item["max_abs_error"]) for item in results if item["max_abs_error"] is not None]
    robustness_scores = [float(item["robustness_score"]) for item in results if item["robustness_score"] is not None]

    return {
        "name": report_name,
        "evaluated_systems": len(results),
        "passed_systems": passed,
        "failed_systems": failed,
        "tolerance": tolerance,
        "failure_categories": dict(sorted(failure_categories.items())),
        "tier_summary": dict(sorted(tier_summary.items())),
        "family_summary": dict(sorted(family_summary.items())),
        "success_rate_by_generated_state_count": dict(sorted(state_count_summary.items(), key=lambda item: int(item[0]))),
        "complexity_by_generated_state_count": complexity_by_state_count,
        "average_rmse": _mean([*rmse_values]) if rmse_values else None,
        "median_rmse": statistics.median(rmse_values) if rmse_values else None,
        "max_rmse": max(rmse_values) if rmse_values else None,
        "average_max_abs_error": _mean([*max_error_values]) if max_error_values else None,
        "max_abs_error": max(max_error_values) if max_error_values else None,
        "average_robustness_score": _mean([*robustness_scores]) if robustness_scores else None,
        "systems": results,
    }


def combine_benchmark_results(
    *,
    legacy_report: dict[str, Any],
    legacy_specs: list[BenchmarkSystemSpec],
    extended_report: dict[str, Any],
    dataset_manifest: dict[str, object],
    baseline_comparison: dict[str, Any],
) -> dict[str, object]:
    """Merge the legacy synthetic benchmark and the additive extension into one report."""
    combined_results = convert_legacy_results(legacy_report, legacy_specs) + list(extended_report["systems"])
    report = _aggregate_report(combined_results, tolerance=float(extended_report["tolerance"]), report_name="SimuCompileBench")
    report["baseline_comparison"] = baseline_comparison
    report["legacy_benchmark_summary"] = {
        "evaluated_systems": legacy_report["evaluated_systems"],
        "passed_systems": legacy_report["passed_systems"],
        "failed_systems": legacy_report["failed_systems"],
        "average_rmse": legacy_report["average_rmse"],
        "average_max_abs_error": legacy_report["average_max_abs_error"],
    }
    report["extended_benchmark_summary"] = {
        "evaluated_systems": extended_report["evaluated_systems"],
        "passed_systems": extended_report["passed_systems"],
        "failed_systems": extended_report["failed_systems"],
    }
    report["dataset_manifest"] = dataset_manifest
    return report


def _csv_rows(report: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in report["systems"]:
        rows.append(
            {
                "system_id": item["system_id"],
                "tier": item["tier"],
                "family": item["family"],
                "generated_state_count": item["generated_state_count"],
                "order": item["order"],
                "depth": item["depth"],
                "nonlinear": item["nonlinear"],
                "trig": item["trig"],
                "expected_failure": item["expected_failure"],
                "overall_pass": item["overall_pass"],
                "benchmark_result": item["benchmark_result"],
                "failure_category": item["failure_category"],
                "failure_stage": item["failure_stage"],
                "rmse": item["rmse"],
                "max_abs_error": item["max_abs_error"],
                "robustness_score": item["robustness_score"],
                "graph_node_count": item["graph_node_count"],
                "simulink_block_count": item["simulink_block_count"],
                "build_time_sec": item["build_time_sec"],
                "simulation_time_sec": item["simulation_time_sec"],
            }
        )
    return rows


def render_simucompilebench_markdown(report: dict[str, Any]) -> str:
    """Render the combined benchmark report as Markdown."""
    lines = [
        "# SimuCompileBench",
        "",
        f"- evaluated systems: {report['evaluated_systems']}",
        f"- passed systems: {report['passed_systems']}",
        f"- failed systems: {report['failed_systems']}",
        f"- tolerance: {report['tolerance']}",
        "",
        "## Baseline Regression Check",
    ]
    baseline = report["baseline_comparison"]
    lines.append(f"- matches baseline: {baseline['matches']}")
    if baseline["mismatches"]:
        for item in baseline["mismatches"]:
            lines.append(f"- mismatch: {item}")

    lines.extend(["", "## Tier Summary"])
    for tier, entry in report["tier_summary"].items():
        lines.append(f"- {tier}: {entry['passed']}/{entry['systems']} ({entry['success_rate']:.1%})")

    lines.extend(["", "## Failure Categories"])
    if report["failure_categories"]:
        for category, count in report["failure_categories"].items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            f"- average RMSE: {report['average_rmse']}",
            f"- median RMSE: {report['median_rmse']}",
            f"- max RMSE: {report['max_rmse']}",
            f"- average max abs error: {report['average_max_abs_error']}",
            f"- max abs error: {report['max_abs_error']}",
            f"- average robustness score: {report['average_robustness_score']}",
            "",
            "## Complexity by Generated State Count",
        ]
    )
    for count_value, entry in report["complexity_by_generated_state_count"].items():
        lines.append(
            f"- {count_value} states: avg graph nodes={entry['average_graph_nodes']}, "
            f"avg Simulink blocks={entry['average_simulink_blocks']}, "
            f"avg build time={entry['average_build_time_sec']}, avg sim time={entry['average_simulation_time_sec']}"
        )

    lines.extend(["", "## System Results"])
    for item in report["systems"]:
        lines.append(f"### {item['system_id']}")
        lines.append(f"- tier: {item['tier']}")
        lines.append(f"- family: {item['family']}")
        lines.append(f"- overall_pass: {item['overall_pass']}")
        lines.append(f"- benchmark_result: {item['benchmark_result']}")
        lines.append(f"- nonlinear: {item['nonlinear']}")
        lines.append(f"- trig: {item['trig']}")
        lines.append(f"- rmse: {item['rmse']}")
        lines.append(f"- max_abs_error: {item['max_abs_error']}")
        lines.append(f"- robustness_score: {item['robustness_score']}")
        if item["failure_category"] is not None:
            lines.append(f"- failure_category: {item['failure_category']}")
        if item["failure_stage"] is not None:
            lines.append(f"- failure_stage: {item['failure_stage']}")
        if item["failure_reason"] is not None:
            lines.append(f"- failure_reason: {item['failure_reason']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_simucompilebench_reports(report: dict[str, Any], *, output_dir: str | Path = "reports") -> dict[str, Any]:
    """Write JSON/CSV/Markdown outputs for the full benchmark."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "simucompilebench.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (target_dir / "simucompilebench.md").write_text(render_simucompilebench_markdown(report), encoding="utf-8")

    rows = _csv_rows(report)
    with (target_dir / "simucompilebench.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    return report
