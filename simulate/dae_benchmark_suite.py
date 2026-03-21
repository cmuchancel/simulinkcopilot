"""Benchmark suite for supported and intentionally unsupported DAE classes."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np

from backend.descriptor_to_simulink import descriptor_to_simulink_model
from backend.graph_to_simulink import graph_to_simulink_model
from backend.simulate_simulink import (
    SimulinkExecutionStageError,
    execute_simulink_descriptor,
    execute_simulink_graph,
    execute_simulink_preserved_dae_graph,
)
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex
from pipeline.run_pipeline import run_pipeline
from repo_paths import REPORTS_ROOT
from simulate.compare import DEFAULT_TOLERANCE
from simulink.engine import start_engine
from states.extract_states import analyze_state_extraction


@dataclass(frozen=True)
class DaeBenchmarkCase:
    """Single DAE benchmark case with expected route semantics."""

    name: str
    category: str
    latex: str
    parameter_values: dict[str, float] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    input_values: dict[str, float] = field(default_factory=dict)
    classification_mode: str = "strict"
    symbol_config: Mapping[str, object] | None = None
    t_span: tuple[float, float] = (0.0, 1.0)
    sample_count: int = 101
    expected_classification_kind: str = "explicit_ode"
    expected_route: str | None = None
    expected_supported: bool = True
    expected_pipeline_success: bool = True
    expected_descriptor_artifact: bool = False
    expected_preserved_form: bool = False
    simulink_lowering_kind: str = "graph"
    expected_failure_substring: str | None = None
    simulink_expected: bool = True


def _stage(status: str, detail: str | None = None) -> dict[str, object]:
    return {"status": status, "detail": detail}


def _default_stages() -> dict[str, dict[str, object]]:
    return {
        "parse": _stage("skipped"),
        "state_extraction": _stage("skipped"),
        "classification": _stage("skipped"),
        "descriptor_artifact": _stage("skipped"),
        "preserved_form": _stage("skipped"),
        "pipeline": _stage("skipped"),
        "python_validation": _stage("skipped"),
        "simulink_lowering": _stage("skipped"),
        "simulink_build": _stage("skipped"),
        "simulink_compare": _stage("skipped"),
    }


def _time_grid(case: DaeBenchmarkCase) -> np.ndarray:
    return np.linspace(case.t_span[0], case.t_span[1], case.sample_count)


def _runtime_override(case: DaeBenchmarkCase) -> dict[str, object]:
    override: dict[str, object] = {
        "parameter_values": dict(case.parameter_values),
        "initial_conditions": dict(case.initial_conditions),
        "input_values": dict(case.input_values),
        "t_span": case.t_span,
        "sample_count": case.sample_count,
    }
    return override


DAE_BENCHMARK_CASES: tuple[DaeBenchmarkCase, ...] = (
    DaeBenchmarkCase(
        name="reducible_nonlinear_helper",
        category="Category 1 - Reducible Semi-Explicit DAEs",
        latex="\n".join([r"\dot{x}=z", r"z+\sin(x)=0"]),
        initial_conditions={"x": 0.2},
        t_span=(0.0, 0.5),
        sample_count=41,
        expected_classification_kind="reducible_semi_explicit_dae",
        expected_route="explicit_ode",
        expected_supported=True,
        expected_preserved_form=False,
        simulink_lowering_kind="graph",
    ),
    DaeBenchmarkCase(
        name="linear_descriptor_capable_balance",
        category="Category 2 - Linear Descriptor-Capable Semi-Explicit DAEs",
        latex="\n".join([r"\dot{x}+y=u", "x+y=1"]),
        initial_conditions={"x": 0.2},
        input_values={"u": 0.0},
        classification_mode="configured",
        symbol_config={"u": "input"},
        t_span=(0.0, 0.5),
        sample_count=41,
        expected_classification_kind="reducible_semi_explicit_dae",
        expected_route="explicit_ode",
        expected_supported=True,
        expected_descriptor_artifact=True,
        expected_preserved_form=False,
        simulink_lowering_kind="descriptor",
    ),
    DaeBenchmarkCase(
        name="nonlinear_preserved_cubic_constraint",
        category="Category 3 - Nonlinear Preserved Semi-Explicit DAEs",
        latex="\n".join([r"\dot{x}=-x+z", r"z^3+z-x=0"]),
        initial_conditions={"x": 0.2},
        t_span=(0.0, 0.5),
        sample_count=41,
        expected_classification_kind="nonlinear_preserved_semi_explicit_dae",
        expected_route="preserved_dae",
        expected_supported=True,
        expected_preserved_form=True,
        simulink_lowering_kind="graph",
    ),
    DaeBenchmarkCase(
        name="unsupported_high_order_preserved_dae",
        category="Category 4 - Unsupported / High-Index DAEs",
        latex="\n".join([r"\ddot{x}+y=0", r"y+\sin(y)-x=0"]),
        initial_conditions={"x": 0.0, "x_dot": 0.0},
        expected_classification_kind="unsupported_dae",
        expected_route="unsupported",
        expected_supported=False,
        expected_pipeline_success=False,
        expected_failure_substring="first-order differential states",
        simulink_expected=False,
    ),
    DaeBenchmarkCase(
        name="unsupported_nonsquare_algebraic_subsystem",
        category="Category 4 - Unsupported / High-Index DAEs",
        latex="\n".join([r"\dot{x}=z", r"z-x=0", r"z+x=1"]),
        initial_conditions={"x": 0.0},
        expected_classification_kind="unsupported_dae",
        expected_route="unsupported",
        expected_supported=False,
        expected_pipeline_success=False,
        expected_failure_substring="structurally singular, non-square, or ambiguously assigned",
        simulink_expected=False,
    ),
)


def _lower_supported_case(
    case: DaeBenchmarkCase,
    result: dict[str, object],
) -> dict[str, object]:
    dae_system = result["dae_system"]
    consistent_initialization = result["consistent_initialization"]
    parameter_values = dict(case.parameter_values)
    input_values = dict(case.input_values)
    if case.simulink_lowering_kind == "descriptor":
        descriptor_system = result["descriptor_system"]
        if descriptor_system is None:
            raise DeterministicCompileError("Descriptor-capable benchmark expected a descriptor artifact.")
        return descriptor_to_simulink_model(
            descriptor_system,
            name=f"{case.name}_descriptor",
            parameter_values=parameter_values,
            input_values=input_values,
            differential_initial_conditions=consistent_initialization.differential_initial_conditions,
            algebraic_initial_conditions=consistent_initialization.algebraic_initial_conditions,
            output_names=[*dae_system.differential_states, *dae_system.algebraic_variables],
        )

    graph = result["graph"]
    if graph is None:
        raise DeterministicCompileError("Supported DAE benchmark expected a lowered graph artifact.")
    if dae_system.reduced_to_explicit:
        requested_outputs = list(dae_system.differential_states)
    else:
        requested_outputs = [*dae_system.differential_states, *dae_system.algebraic_variables]
    if not requested_outputs and result["first_order"] is not None:
        requested_outputs = list(result["first_order"]["states"])  # type: ignore[index]
    return graph_to_simulink_model(
        graph,
        name=f"{case.name}_graph",
        state_names=requested_outputs or None,
        parameter_values=parameter_values,
        input_values=input_values,
        initial_conditions=consistent_initialization.differential_initial_conditions,
        algebraic_initial_conditions=consistent_initialization.algebraic_initial_conditions,
    )


def _execute_supported_case(
    case: DaeBenchmarkCase,
    result: dict[str, object],
    *,
    eng,
    tolerance: float,
) -> object:
    dae_system = result["dae_system"]
    consistent_initialization = result["consistent_initialization"]
    runtime = result["runtime"]
    output_names = [*dae_system.differential_states, *dae_system.algebraic_variables]
    if case.simulink_lowering_kind == "descriptor":
        descriptor_system = result["descriptor_system"]
        if descriptor_system is None:
            raise DeterministicCompileError("Descriptor-capable benchmark expected a descriptor artifact.")
        return execute_simulink_descriptor(
            eng,
            descriptor_system=descriptor_system,
            name=f"{case.name}_simulink",
            parameter_values=dict(case.parameter_values),
            differential_initial_conditions=consistent_initialization.differential_initial_conditions,
            algebraic_initial_conditions=consistent_initialization.algebraic_initial_conditions,
            t_span=runtime["t_span"],  # type: ignore[arg-type]
            t_eval=runtime["t_eval"],  # type: ignore[arg-type]
            output_names=output_names,
            input_values=dict(case.input_values),
            output_dir=REPORTS_ROOT / "dae_benchmark_models",
        )

    graph = result["graph"]
    if graph is None:
        raise DeterministicCompileError("Supported DAE benchmark expected a lowered graph artifact.")
    if result["first_order"] is not None:
        return execute_simulink_graph(
            eng,
            graph=graph,
            name=f"{case.name}_simulink",
            state_names=list(result["first_order"]["states"]),  # type: ignore[index]
            parameter_values=dict(case.parameter_values),
            initial_conditions=dict(case.initial_conditions),
            t_span=runtime["t_span"],  # type: ignore[arg-type]
            t_eval=runtime["t_eval"],  # type: ignore[arg-type]
            input_values=dict(case.input_values),
            ode_result=result["ode_result"],
            state_space_result=result["state_space_result"],
            tolerance=tolerance,
            output_dir=REPORTS_ROOT / "dae_benchmark_models",
        )
    return execute_simulink_preserved_dae_graph(
        eng,
        graph=graph,
        name=f"{case.name}_simulink",
        output_names=output_names,
        parameter_values=dict(case.parameter_values),
        differential_initial_conditions=consistent_initialization.differential_initial_conditions,
        algebraic_initial_conditions=consistent_initialization.algebraic_initial_conditions,
        t_span=runtime["t_span"],  # type: ignore[arg-type]
        t_eval=runtime["t_eval"],  # type: ignore[arg-type]
        input_values=dict(case.input_values),
        output_dir=REPORTS_ROOT / "dae_benchmark_models",
    )


def run_dae_benchmark(
    *,
    selected_cases: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = False,
) -> dict[str, object]:
    """Run the DAE benchmark suite and return a structured report."""
    selected = set(selected_cases or [case.name for case in DAE_BENCHMARK_CASES])
    cases = [case for case in DAE_BENCHMARK_CASES if case.name in selected]

    eng = None
    engine_error: str | None = None
    if run_simulink and any(case.expected_pipeline_success and case.simulink_expected for case in cases):
        try:
            eng = start_engine(retries=1, retry_delay_seconds=1.0)
        except Exception as exc:  # pragma: no cover - environment dependent
            engine_error = str(exc)

    results: list[dict[str, object]] = []
    try:
        for case in cases:
            stages = _default_stages()
            metrics: dict[str, object] = {
                "classification_kind": None,
                "classification_route": None,
                "differential_state_count": None,
                "algebraic_variable_count": None,
                "reduced_to_explicit": None,
                "descriptor_artifact_available": None,
                "preserved_form_available": None,
                "graph_nodes": None,
                "lowered_simulink_blocks": None,
                "residual_norm_max": None,
                "residual_norm_final": None,
            }
            failure_stage: str | None = None
            failure_reason: str | None = None
            analysis = None
            result = None
            simulink_validation = None

            try:
                equations = translate_latex(case.latex)
                stages["parse"] = _stage("passed")
            except Exception as exc:
                failure_stage = "parse"
                failure_reason = str(exc)
                stages["parse"] = _stage("failed", str(exc))
                results.append(
                    {
                        "name": case.name,
                        "category": case.category,
                        "latex": case.latex,
                        "classification": classification,
                        "stages": stages,
                        "metrics": metrics,
                        "failure_stage": failure_stage,
                        "failure_reason": failure_reason,
                        "overall_pass": False,
                    }
                )
                continue

            try:
                analysis = analyze_state_extraction(
                    equations,
                    mode=case.classification_mode,
                    symbol_config=case.symbol_config,
                )
                stages["state_extraction"] = _stage("passed")
            except Exception as exc:
                failure_stage = "state_extraction"
                failure_reason = str(exc)
                stages["state_extraction"] = _stage("failed", str(exc))
                results.append(
                    {
                        "name": case.name,
                        "category": case.category,
                        "latex": case.latex,
                        "stages": stages,
                        "metrics": metrics,
                        "failure_stage": failure_stage,
                        "failure_reason": failure_reason,
                        "overall_pass": False,
                    }
                )
                continue

            classification = analysis.dae_system.classification.to_dict()
            metrics["classification_kind"] = classification["kind"]
            metrics["classification_route"] = classification["route"]
            metrics["differential_state_count"] = len(analysis.dae_system.differential_states)
            metrics["algebraic_variable_count"] = len(analysis.dae_system.algebraic_variables)
            metrics["reduced_to_explicit"] = analysis.dae_system.reduced_to_explicit
            metrics["descriptor_artifact_available"] = analysis.descriptor_system is not None
            metrics["preserved_form_available"] = analysis.dae_system.preserved_form is not None

            classification_matches = (
                classification["kind"] == case.expected_classification_kind
                and classification["supported"] is case.expected_supported
                and (case.expected_route is None or classification["route"] == case.expected_route)
            )
            if not classification_matches:
                failure_stage = "classification"
                failure_reason = (
                    f"Expected kind={case.expected_classification_kind!r}, route={case.expected_route!r}, "
                    f"supported={case.expected_supported!r}; got {classification!r}."
                )
                stages["classification"] = _stage("failed", failure_reason)
                results.append(
                    {
                        "name": case.name,
                        "category": case.category,
                        "latex": case.latex,
                        "stages": stages,
                        "metrics": metrics,
                        "failure_stage": failure_stage,
                        "failure_reason": failure_reason,
                        "overall_pass": False,
                    }
                )
                continue
            stages["classification"] = _stage("passed", classification["kind"])

            if case.expected_descriptor_artifact:
                if analysis.descriptor_system is None:
                    failure_stage = "descriptor_artifact"
                    failure_reason = "Expected descriptor artifact was unavailable."
                    stages["descriptor_artifact"] = _stage("failed", failure_reason)
                    results.append(
                        {
                            "name": case.name,
                            "category": case.category,
                            "latex": case.latex,
                            "classification": classification,
                            "stages": stages,
                            "metrics": metrics,
                            "failure_stage": failure_stage,
                            "failure_reason": failure_reason,
                            "overall_pass": False,
                        }
                    )
                    continue
                stages["descriptor_artifact"] = _stage("passed")
            else:
                stages["descriptor_artifact"] = _stage("skipped", "descriptor artifact not required")

            if case.expected_preserved_form:
                if analysis.dae_system.preserved_form is None:
                    failure_stage = "preserved_form"
                    failure_reason = "Expected preserved semi-explicit DAE form was unavailable."
                    stages["preserved_form"] = _stage("failed", failure_reason)
                    results.append(
                        {
                            "name": case.name,
                            "category": case.category,
                            "latex": case.latex,
                            "classification": classification,
                            "stages": stages,
                            "metrics": metrics,
                            "failure_stage": failure_stage,
                            "failure_reason": failure_reason,
                            "overall_pass": False,
                        }
                    )
                    continue
                stages["preserved_form"] = _stage("passed")
            else:
                stages["preserved_form"] = _stage("skipped", "preserved DAE form not required")

            with tempfile.TemporaryDirectory() as temp_dir:
                case_path = Path(temp_dir) / f"{case.name}.tex"
                case_path.write_text(case.latex, encoding="utf-8")
                try:
                    result = run_pipeline(
                        case_path,
                        tolerance=tolerance,
                        run_sim=True,
                        validate_graph=True,
                        run_simulink=False,
                        runtime_override=_runtime_override(case),
                        classification_mode=case.classification_mode,
                        symbol_config=case.symbol_config,
                    )
                    stages["pipeline"] = _stage("passed", result["dae_classification"]["route"])  # type: ignore[index]
                except Exception as exc:
                    failure_stage = "pipeline"
                    failure_reason = str(exc)
                    if not case.expected_pipeline_success and (
                        case.expected_failure_substring is None
                        or case.expected_failure_substring.lower() in str(exc).lower()
                    ):
                        stages["pipeline"] = _stage("expected_failure", str(exc))
                        results.append(
                            {
                                "name": case.name,
                                "category": case.category,
                                "latex": case.latex,
                                "classification": classification,
                                "stages": stages,
                                "metrics": metrics,
                                "failure_stage": failure_stage,
                                "failure_reason": failure_reason,
                                "overall_pass": True,
                            }
                        )
                        continue
                    stages["pipeline"] = _stage("failed", str(exc))
                    results.append(
                        {
                            "name": case.name,
                            "category": case.category,
                            "latex": case.latex,
                            "classification": classification,
                            "stages": stages,
                            "metrics": metrics,
                            "failure_stage": failure_stage,
                            "failure_reason": failure_reason,
                            "overall_pass": False,
                        }
                    )
                    continue

                dae_validation = result["dae_validation"]
                if dae_validation is None:
                    failure_stage = "python_validation"
                    failure_reason = "Supported DAE benchmark did not produce DAE-native validation output."
                    stages["python_validation"] = _stage("failed", failure_reason)
                    results.append(
                        {
                            "name": case.name,
                            "category": case.category,
                            "latex": case.latex,
                            "classification": classification,
                            "stages": stages,
                            "metrics": metrics,
                            "failure_stage": failure_stage,
                            "failure_reason": failure_reason,
                            "overall_pass": False,
                        }
                    )
                    continue
                metrics["residual_norm_max"] = dae_validation.get("residual_norm_max")
                metrics["residual_norm_final"] = dae_validation.get("residual_norm_final")
                if not bool(dae_validation["simulation_success"]):
                    failure_stage = "python_validation"
                    failure_reason = str(dae_validation.get("message") or "DAE validation failed.")
                    stages["python_validation"] = _stage("failed", failure_reason)
                    results.append(
                        {
                            "name": case.name,
                            "category": case.category,
                            "latex": case.latex,
                            "classification": classification,
                            "stages": stages,
                            "metrics": metrics,
                            "failure_stage": failure_stage,
                            "failure_reason": failure_reason,
                            "overall_pass": False,
                        }
                    )
                    continue
                stages["python_validation"] = _stage(
                    "passed",
                    f"residual_max={float(dae_validation['residual_norm_max']):.3e}",
                )

                try:
                    lowered_model = _lower_supported_case(case, result)
                    metrics["lowered_simulink_blocks"] = len(lowered_model["blocks"])  # type: ignore[index]
                    if result["graph"] is not None:
                        metrics["graph_nodes"] = len(result["graph"]["nodes"])  # type: ignore[index]
                    stages["simulink_lowering"] = _stage("passed", lowered_model["name"])  # type: ignore[index]
                except Exception as exc:
                    failure_stage = "simulink_lowering"
                    failure_reason = str(exc)
                    stages["simulink_lowering"] = _stage("failed", str(exc))
                    results.append(
                        {
                            "name": case.name,
                            "category": case.category,
                            "latex": case.latex,
                            "classification": classification,
                            "stages": stages,
                            "metrics": metrics,
                            "failure_stage": failure_stage,
                            "failure_reason": failure_reason,
                            "overall_pass": False,
                        }
                    )
                    continue

                if not case.simulink_expected:
                    stages["simulink_build"] = _stage("skipped", "Simulink execution not expected")
                    stages["simulink_compare"] = _stage("skipped", "Simulink execution not expected")
                elif not run_simulink:
                    stages["simulink_build"] = _stage("skipped", "Simulink benchmark disabled")
                    stages["simulink_compare"] = _stage("skipped", "Simulink benchmark disabled")
                elif engine_error is not None or eng is None:
                    failure_stage = "simulink_build"
                    failure_reason = engine_error or "MATLAB engine unavailable"
                    stages["simulink_build"] = _stage("failed", failure_reason)
                    stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                else:
                    try:
                        execution = _execute_supported_case(
                            case,
                            result,
                            eng=eng,
                            tolerance=tolerance,
                        )
                        stages["simulink_build"] = _stage("passed", execution.model_file)
                        validation = execution.validation
                        simulink_validation = validation
                        if validation is None:
                            stages["simulink_compare"] = _stage("skipped", "no validation artifact")
                        elif validation["passes"]:
                            stages["simulink_compare"] = _stage("passed")
                        else:
                            stages["simulink_compare"] = _stage("failed", json.dumps(validation))
                    except SimulinkExecutionStageError as exc:
                        failure_stage = exc.stage
                        failure_reason = str(exc)
                        stages["simulink_build"] = _stage("failed", str(exc))
                        stages["simulink_compare"] = _stage("skipped", "Simulink build failed")
                    except Exception as exc:
                        failure_stage = "simulink_build"
                        failure_reason = str(exc)
                        stages["simulink_build"] = _stage("failed", str(exc))
                        stages["simulink_compare"] = _stage("skipped", "Simulink build failed")

            overall_pass = all(
                stages[name]["status"] in {"passed", "skipped", "expected_failure"}
                for name in stages
            )
            if stages["simulink_compare"]["status"] == "failed":
                overall_pass = False
            results.append(
                {
                    "name": case.name,
                    "category": case.category,
                    "latex": case.latex,
                    "classification": classification,
                    "metrics": metrics,
                    "stages": stages,
                    "failure_stage": failure_stage,
                    "failure_reason": failure_reason,
                    "simulink_validation": simulink_validation,
                    "overall_pass": overall_pass,
                }
            )
    finally:
        if eng is not None:
            eng.quit()

    passed = sum(1 for result in results if result["overall_pass"])
    return {
        "generated_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "tolerance": tolerance,
        "categories": sorted({case.category for case in cases}),
        "cases": results,
    }


def render_dae_benchmark_markdown(report: dict[str, object]) -> str:
    """Render the DAE benchmark report as Markdown."""
    lines = [
        "# DAE Benchmark",
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
            classification = case.get("classification")
            if classification is not None:
                lines.append(f"- classification: {classification['kind']} via {classification['route']}")
            metrics = case["metrics"]
            lines.append(f"- differential_state_count: {metrics['differential_state_count']}")
            lines.append(f"- algebraic_variable_count: {metrics['algebraic_variable_count']}")
            lines.append(f"- reduced_to_explicit: {metrics['reduced_to_explicit']}")
            lines.append(f"- descriptor_artifact_available: {metrics['descriptor_artifact_available']}")
            lines.append(f"- preserved_form_available: {metrics['preserved_form_available']}")
            lines.append(f"- graph_nodes: {metrics['graph_nodes']}")
            lines.append(f"- lowered_simulink_blocks: {metrics['lowered_simulink_blocks']}")
            lines.append(f"- residual_norm_max: {metrics['residual_norm_max']}")
            lines.append(f"- residual_norm_final: {metrics['residual_norm_final']}")
            if case["failure_stage"] is not None:
                lines.append(f"- failure_stage: {case['failure_stage']}")
            if case["failure_reason"] is not None:
                lines.append(f"- failure_reason: {case['failure_reason']}")
            for stage_name, stage in case["stages"].items():
                detail = f" ({stage['detail']})" if stage["detail"] else ""
                lines.append(f"- {stage_name}: {stage['status']}{detail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_dae_benchmark_reports(
    output_dir: str | Path = REPORTS_ROOT,
    *,
    selected_cases: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = False,
) -> dict[str, object]:
    """Run the DAE benchmark suite and write JSON/Markdown reports."""
    report = run_dae_benchmark(
        selected_cases=selected_cases,
        tolerance=tolerance,
        run_simulink=run_simulink,
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "dae_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_path / "dae_benchmark.md").write_text(
        render_dae_benchmark_markdown(report),
        encoding="utf-8",
    )
    return report
