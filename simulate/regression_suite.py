"""Regression harness for bundled deterministic compiler examples."""

from __future__ import annotations

import json
from pathlib import Path

from examples.catalog import EXAMPLE_SPECS, example_paths
from pipeline.run_pipeline import run_pipeline, summarize_pipeline_results
from simulate.compare import DEFAULT_TOLERANCE
from simulink.engine import start_engine


SUPPORTED_SYNTAX = [
    r"\dot{x}",
    r"\ddot{x}",
    r"\frac{d^n x}{dt^n} for explicit integer n",
    r"\frac{...}{...} including nested fractions",
    "implicit multiplication such as 2x, k(x-y), m\\frac{dx}{dt}",
    "indexed symbols such as x_1, x_2, k_12",
    r"\left...\right normalization",
]

SUPPORTED_SYSTEM_CLASSES = [
    "linear first-order ODE systems",
    "linear higher-order ODE systems reduced to first-order form",
    "coupled multi-state linear systems",
    "mixed first/second-order systems",
    "explicit nonlinear polynomial first-order systems",
]

KNOWN_UNSUPPORTED_CLASSES = [
    "DAE-like algebraic constraints mixed with differential equations",
    "implicit nonlinear derivative coupling with non-unique solves",
    "unsupported LaTeX commands outside the restricted grammar",
    "nonlinear systems in state-space conversion",
]

SIMULINK_REGRESSION_EXAMPLES = {
    "mass_spring_damper",
    "two_mass_coupled",
    "three_mass_coupled",
    "driven_oscillator",
    "damped_forced_system",
}


def _stage(status: str, detail: str | None = None) -> dict[str, object]:
    return {"status": status, "detail": detail}


def run_regression_suite(
    *,
    selected_examples: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
) -> dict[str, object]:
    """Run the regression suite across the bundled examples."""
    selected = set(selected_examples or EXAMPLE_SPECS)
    example_results: list[dict[str, object]] = []
    graph_ops: set[str] = set()
    passed_examples = 0

    engine_error: str | None = None
    eng = None
    if run_simulink and any(name in selected for name in SIMULINK_REGRESSION_EXAMPLES):
        try:
            eng = start_engine(retries=1, retry_delay_seconds=1.0)
        except Exception as exc:  # pragma: no cover - environment dependent
            engine_error = str(exc)

    try:
        for path in example_paths():
            stem = path.stem
            if stem not in selected:
                continue

            spec = EXAMPLE_SPECS[stem]
            use_simulink = run_simulink and stem in SIMULINK_REGRESSION_EXAMPLES

            if use_simulink and engine_error is not None:
                example_results.append(
                    {
                        "name": stem,
                        "path": str(path),
                        "expected_linear": spec.expected_linear,
                        "error": engine_error,
                        "stages": {
                            "simulink_build": _stage("failed", engine_error),
                        },
                        "overall_pass": False,
                    }
                )
                continue

            try:
                results = run_pipeline(
                    path,
                    tolerance=tolerance,
                    run_sim=True,
                    validate_graph=True,
                    run_simulink=use_simulink,
                    matlab_engine=eng,
                )
                summary = summarize_pipeline_results(results)
                graph_ops.update(summary["graph"]["ops"])

                comparison = results["comparison"]
                inferred_linear = bool(summary["linearity"]["is_linear"])
                compare_stage = (
                    _stage("passed", f"rmse={comparison['rmse']:.3e}, max={comparison['max_abs_error']:.3e}")
                    if comparison is not None and comparison["passes"]
                    else _stage("skipped", "state-space comparison not available")
                )
                if comparison is not None and not comparison["passes"]:
                    compare_stage = _stage("failed", f"rmse={comparison['rmse']:.3e}, max={comparison['max_abs_error']:.3e}")

                state_space_stage = (
                    _stage("passed")
                    if results["state_space"] is not None
                    else _stage(
                        "skipped" if not spec.expected_linear else "failed",
                        "nonlinear explicit system" if not spec.expected_linear else "expected linear state-space form was unavailable",
                    )
                )

                simulink_validation = results["simulink_validation"]
                simulink_build_stage = (
                    _stage("passed", results["simulink_result"]["model_file"])  # type: ignore[index]
                    if use_simulink and results["simulink_result"] is not None
                    else _stage("skipped", "Simulink backend not requested")
                )
                simulink_compare_stage = (
                    _stage(
                        "passed",
                        f"rmse={simulink_validation['vs_ode']['rmse']:.3e}, max={simulink_validation['vs_ode']['max_abs_error']:.3e}",
                    )
                    if simulink_validation is not None and simulink_validation["passes"]
                    else _stage("skipped", "Simulink backend not requested")
                )
                if simulink_validation is not None and not simulink_validation["passes"]:
                    simulink_compare_stage = _stage(
                        "failed",
                        f"rmse={simulink_validation['vs_ode']['rmse']:.3e}, max={simulink_validation['vs_ode']['max_abs_error']:.3e}",
                    )

                stages = {
                    "parse": _stage("passed"),
                    "state_extraction": _stage("passed"),
                    "solve": _stage("passed"),
                    "first_order": _stage("passed"),
                    "graph_lowering": _stage("passed"),
                    "graph_validation": _stage("passed"),
                    "ode_simulation": _stage("passed"),
                    "state_space": state_space_stage,
                    "comparison": compare_stage,
                    "simulink_build": simulink_build_stage,
                    "simulink_compare": simulink_compare_stage,
                }
                overall_pass = (
                    inferred_linear == spec.expected_linear
                    and state_space_stage["status"] != "failed"
                    and compare_stage["status"] != "failed"
                    and simulink_build_stage["status"] != "failed"
                    and simulink_compare_stage["status"] != "failed"
                )
                if overall_pass:
                    passed_examples += 1

                example_results.append(
                    {
                        "name": stem,
                        "path": str(path),
                        "expected_linear": spec.expected_linear,
                        "linearity": summary["linearity"],
                        "graph": summary["graph"],
                        "comparison": summary["comparison"],
                        "simulink": summary["simulink"],
                        "stages": stages,
                        "overall_pass": overall_pass,
                    }
                )
            except Exception as exc:  # pragma: no cover - exercised in generated report if failures appear
                example_results.append(
                    {
                        "name": stem,
                        "path": str(path),
                        "expected_linear": spec.expected_linear,
                        "error": str(exc),
                        "stages": {
                            "parse": _stage("failed", str(exc)),
                        },
                        "overall_pass": False,
                    }
                )
    finally:
        if eng is not None:
            eng.quit()

    report = {
        "generated_examples": len(example_results),
        "passed_examples": passed_examples,
        "failed_examples": len(example_results) - passed_examples,
        "supported_syntax": SUPPORTED_SYNTAX,
        "supported_system_classes": SUPPORTED_SYSTEM_CLASSES,
        "known_unsupported_classes": KNOWN_UNSUPPORTED_CLASSES,
        "graph_lowering_coverage": sorted(graph_ops),
        "simulink_examples": sorted(SIMULINK_REGRESSION_EXAMPLES),
        "examples": example_results,
        "tolerance": tolerance,
    }
    return report


def render_markdown_report(report: dict[str, object]) -> str:
    """Render the regression report as Markdown."""
    lines = [
        "# Phase 3 Report",
        "",
        f"- examples run: {report['generated_examples']}",
        f"- passed: {report['passed_examples']}",
        f"- failed: {report['failed_examples']}",
        f"- tolerance: {report['tolerance']}",
        "",
        "## Supported Syntax",
    ]
    lines.extend(f"- {entry}" for entry in report["supported_syntax"])
    lines.extend(
        [
            "",
            "## Supported System Classes",
        ]
    )
    lines.extend(f"- {entry}" for entry in report["supported_system_classes"])
    lines.extend(
        [
            "",
            "## Known Unsupported Classes",
        ]
    )
    lines.extend(f"- {entry}" for entry in report["known_unsupported_classes"])
    lines.extend(
        [
            "",
            "## Graph Lowering Coverage",
            f"- ops: {', '.join(report['graph_lowering_coverage'])}",
            "",
            "## Simulink Regression Examples",
        ]
    )
    lines.extend(f"- {entry}" for entry in report["simulink_examples"])
    lines.extend(
        [
            "",
            "## Example Results",
        ]
    )

    for example in report["examples"]:
        lines.append(f"### {example['name']}")
        lines.append(f"- overall_pass: {example['overall_pass']}")
        if "error" in example:
            lines.append(f"- error: {example['error']}")
            continue
        linearity = example["linearity"]
        lines.append(f"- expected_linear: {example['expected_linear']}")
        lines.append(f"- inferred_linear: {linearity['is_linear']}")
        for stage_name, stage in example["stages"].items():
            detail = f" ({stage['detail']})" if stage["detail"] else ""
            lines.append(f"- {stage_name}: {stage['status']}{detail}")
        lines.append(f"- graph_ops: {', '.join(example['graph']['ops'])}")

    return "\n".join(lines) + "\n"


def write_regression_reports(
    output_dir: str | Path = "reports",
    *,
    selected_examples: list[str] | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = True,
) -> dict[str, object]:
    """Run the regression suite and write JSON/Markdown reports."""
    report = run_regression_suite(
        selected_examples=selected_examples,
        tolerance=tolerance,
        run_simulink=run_simulink,
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for stem in ["phase2_report", "phase3_report"]:
        (output_path / f"{stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output_path / f"{stem}.md").write_text(render_markdown_report(report), encoding="utf-8")
    return report
