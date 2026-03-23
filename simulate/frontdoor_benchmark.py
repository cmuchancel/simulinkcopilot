"""Cross-front-door benchmark harness for latex, matlab_symbolic, and matlab_equation_text."""

from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import sympy

from ir.equation_dict import equation_to_residual, equation_to_string
from ir.expression_nodes import SymbolNode, walk_expression
from latex_frontend.symbols import parse_derivative_symbol_name
from latex_frontend.translator import translate_latex
from pipeline.run_pipeline import run_pipeline_payload
from repo_paths import DATA_ROOT, REPORTS_ROOT
from simulate.compare import DEFAULT_TOLERANCE, compare_simulations
from simulate.synthetic_benchmark import (
    DEFAULT_SYNTHETIC_SEED,
    DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    STATE_VARS,
    SyntheticSystemSpec,
    generate_synthetic_systems,
)


FRONT_DOORS = ("latex", "matlab_symbolic", "matlab_equation_text")
_CANONICAL_DERIVATIVE_RE = re.compile(r"\bD(?P<order>\d+)_(?P<base>[A-Za-z][A-Za-z0-9_]*)\b")


@dataclass(frozen=True)
class FrontDoorPayloads:
    """All benchmark payload variants for a single synthetic system."""

    system_id: str
    family: str
    states: tuple[str, ...]
    inputs: tuple[str, ...]
    parameters: tuple[str, ...]
    latex_text: str
    canonical_equations: tuple[str, ...]
    matlab_symbolic_equations: tuple[str, ...]
    matlab_equation_text_equations: tuple[str, ...]
    runtime_override: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "system_id": self.system_id,
            "family": self.family,
            "states": list(self.states),
            "inputs": list(self.inputs),
            "parameters": list(self.parameters),
            "latex_text": self.latex_text,
            "canonical_equations": list(self.canonical_equations),
            "matlab_symbolic_equations": list(self.matlab_symbolic_equations),
            "matlab_equation_text_equations": list(self.matlab_equation_text_equations),
            "runtime_override": self.runtime_override,
        }


def _base_states_for_spec(spec: SyntheticSystemSpec) -> tuple[str, ...]:
    return tuple(STATE_VARS[: spec.generated_state_count])


def _canonical_to_symbolic(text: str, time_variable: str = "t") -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        parsed = parse_derivative_symbol_name(token)
        if parsed is None:
            return token
        base, order = parsed
        if order == 1:
            return f"diff({base},{time_variable})"
        return f"diff({base},{time_variable},{order})"

    return _CANONICAL_DERIVATIVE_RE.sub(replace, text).replace(" = ", " == ")


def build_frontdoor_payloads(spec: SyntheticSystemSpec) -> FrontDoorPayloads:
    """Build equivalent payloads for all three front doors from one latex synthetic system."""
    equations = translate_latex(spec.latex)
    canonical_equations = tuple(equation_to_string(item) for item in equations)
    base_states = _base_states_for_spec(spec)
    used_symbols = {
        node.name
        for equation in equations
        for side in (equation.lhs, equation.rhs)
        for node in walk_expression(side)
        if isinstance(node, SymbolNode)
    }
    inputs = tuple(sorted(name for name, role in spec.symbol_config.items() if role == "input" and name in used_symbols))
    parameters = tuple(
        sorted(name for name, role in spec.symbol_config.items() if role == "parameter" and name in used_symbols)
    )
    runtime_override = {
        "parameter_values": dict(spec.parameter_values),
        "initial_conditions": dict(spec.initial_conditions),
        "input_values": dict(spec.input_values),
        "t_span": list(spec.t_span),
        "sample_count": spec.sample_count,
    }
    return FrontDoorPayloads(
        system_id=spec.system_id,
        family=spec.family,
        states=base_states,
        inputs=inputs,
        parameters=parameters,
        latex_text=spec.latex,
        canonical_equations=canonical_equations,
        matlab_symbolic_equations=tuple(_canonical_to_symbolic(text) for text in canonical_equations),
        matlab_equation_text_equations=canonical_equations,
        runtime_override=runtime_override,
    )


def _payload_for_frontdoor(payloads: FrontDoorPayloads, source_type: str) -> dict[str, object]:
    common: dict[str, object] = {
        "source_type": source_type,
        "name": payloads.system_id,
        "states": list(payloads.states),
        "inputs": list(payloads.inputs),
        "parameters": list(payloads.parameters),
        "time_variable": "t",
    }
    if source_type == "latex":
        common["text"] = payloads.latex_text
    elif source_type == "matlab_symbolic":
        common["equations"] = list(payloads.matlab_symbolic_equations)
    elif source_type == "matlab_equation_text":
        common["equations"] = list(payloads.matlab_equation_text_equations)
    else:
        raise ValueError(f"Unsupported front door {source_type!r}.")
    return common


def _frontdoor_row(
    payloads: FrontDoorPayloads,
    *,
    source_type: str,
    status: str,
    duration_sec: float,
    failure_reason: str | None,
    normalized_equations: tuple[str, ...] | None,
    state_count: int | None,
    graph_node_count: int | None,
    ode_rmse_vs_latex: float | None,
    ode_max_abs_vs_latex: float | None,
) -> dict[str, object]:
    return {
        "system_id": payloads.system_id,
        "family": payloads.family,
        "source_type": source_type,
        "status": status,
        "duration_sec": duration_sec,
        "failure_reason": failure_reason,
        "normalized_equations": list(normalized_equations) if normalized_equations is not None else None,
        "state_count": state_count,
        "graph_node_count": graph_node_count,
        "ode_rmse_vs_latex": ode_rmse_vs_latex,
        "ode_max_abs_vs_latex": ode_max_abs_vs_latex,
    }


def _semantic_equation_signature(result: dict[str, object]) -> tuple[str, ...]:
    problem = result["normalized_problem"]
    return tuple(
        sympy.sstr(
            sympy.together(
                sympy.expand(
                    sympy.nsimplify(equation_to_residual(equation), rational=True)
                )
            )
        )
        for equation in problem.equation_nodes()
    )


def run_frontdoor_benchmark(
    systems: list[SyntheticSystemSpec] | None = None,
    *,
    count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    seed: int = DEFAULT_SYNTHETIC_SEED,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = False,
    progress_callback: Callable[[int, int, dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Run the same synthetic systems through the latex, matlab_symbolic, and matlab_equation_text front doors."""
    systems = list(systems or generate_synthetic_systems(count=count, seed=seed))
    payload_sets = [build_frontdoor_payloads(spec) for spec in systems]
    rows: list[dict[str, object]] = []
    system_summaries: list[dict[str, object]] = []

    for index, payloads in enumerate(payload_sets, start=1):
        frontdoor_results: dict[str, dict[str, object]] = {}
        frontdoor_rows: dict[str, dict[str, object]] = {}

        for source_type in FRONT_DOORS:
            started = time.perf_counter()
            try:
                result = run_pipeline_payload(
                    _payload_for_frontdoor(payloads, source_type),
                    run_sim=True,
                    run_simulink=run_simulink,
                    runtime_override=payloads.runtime_override,
                    tolerance=tolerance,
                )
                duration_sec = time.perf_counter() - started
                normalized_equations = tuple(equation_to_string(item) for item in result["normalized_problem"].equation_nodes())
                graph = result["graph"]
                row = _frontdoor_row(
                    payloads,
                    source_type=source_type,
                    status="passed",
                    duration_sec=duration_sec,
                    failure_reason=None,
                    normalized_equations=normalized_equations,
                    state_count=len(result["extraction"].states),
                    graph_node_count=(len(graph["nodes"]) if graph is not None else None),
                    ode_rmse_vs_latex=None,
                    ode_max_abs_vs_latex=None,
                )
                frontdoor_results[source_type] = result
            except Exception as exc:
                duration_sec = time.perf_counter() - started
                row = _frontdoor_row(
                    payloads,
                    source_type=source_type,
                    status="failed",
                    duration_sec=duration_sec,
                    failure_reason=str(exc),
                    normalized_equations=None,
                    state_count=None,
                    graph_node_count=None,
                    ode_rmse_vs_latex=None,
                    ode_max_abs_vs_latex=None,
                )
            frontdoor_rows[source_type] = row

        if "latex" in frontdoor_results:
            latex_ode = frontdoor_results["latex"]["ode_result"]
            for source_type in FRONT_DOORS:
                if source_type == "latex" or source_type not in frontdoor_results:
                    continue
                comparison = compare_simulations(
                    latex_ode,
                    frontdoor_results[source_type]["ode_result"],
                    tolerance=tolerance,
                )
                frontdoor_rows[source_type]["ode_rmse_vs_latex"] = comparison["rmse"]
                frontdoor_rows[source_type]["ode_max_abs_vs_latex"] = comparison["max_abs_error"]

        rows.extend(frontdoor_rows[source_type] for source_type in FRONT_DOORS)

        successful_normalizations = {
            _semantic_equation_signature(frontdoor_results[source_type])
            for source_type in FRONT_DOORS
            if source_type in frontdoor_results
        }
        system_summary = {
            "system_id": payloads.system_id,
            "family": payloads.family,
            "all_frontdoors_passed": all(row["status"] == "passed" for row in frontdoor_rows.values()),
            "normalized_equations_match": len(successful_normalizations) <= 1,
            "rows": {source_type: frontdoor_rows[source_type] for source_type in FRONT_DOORS},
        }
        system_summaries.append(system_summary)
        if progress_callback is not None:
            progress_callback(index, len(payload_sets), system_summary)

    success_by_source = {
        source_type: {
            "passed": sum(1 for row in rows if row["source_type"] == source_type and row["status"] == "passed"),
            "evaluated": sum(1 for row in rows if row["source_type"] == source_type),
        }
        for source_type in FRONT_DOORS
    }
    for item in success_by_source.values():
        item["success_rate"] = (item["passed"] / item["evaluated"]) if item["evaluated"] else 0.0

    report = {
        "benchmark_name": "frontdoor_equivalence_benchmark",
        "generated_systems": len(payload_sets),
        "evaluated_frontdoor_runs": len(rows),
        "front_doors": list(FRONT_DOORS),
        "systems": system_summaries,
        "rows": rows,
        "success_by_source_type": success_by_source,
        "all_frontdoors_passed_systems": sum(1 for item in system_summaries if item["all_frontdoors_passed"]),
        "normalized_match_systems": sum(1 for item in system_summaries if item["normalized_equations_match"]),
        "average_duration_sec": (
            sum(float(row["duration_sec"]) for row in rows) / len(rows) if rows else 0.0
        ),
        "average_rmse_vs_latex": (
            sum(
                float(row["ode_rmse_vs_latex"])
                for row in rows
                if row["ode_rmse_vs_latex"] is not None
            )
            / max(1, sum(1 for row in rows if row["ode_rmse_vs_latex"] is not None))
        ),
        "tolerance": tolerance,
        "run_simulink": run_simulink,
    }
    return report


def render_frontdoor_benchmark_markdown(report: dict[str, object]) -> str:
    """Render the cross-front-door benchmark report as Markdown."""
    lines = [
        "# Front-Door Benchmark",
        "",
        f"- Generated systems: {report['generated_systems']}",
        f"- Front-door evaluations: {report['evaluated_frontdoor_runs']}",
        f"- All-front-doors-passed systems: {report['all_frontdoors_passed_systems']}",
        f"- Normalized-equation matches: {report['normalized_match_systems']}",
        f"- Average duration (sec): {report['average_duration_sec']:.6f}",
        f"- Average ODE RMSE vs latex baseline: {report['average_rmse_vs_latex']:.6e}",
        "",
        "## Success By Front Door",
        "",
        "| Front door | Passed | Evaluated | Success rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for source_type, summary in report["success_by_source_type"].items():
        lines.append(
            f"| {source_type} | {summary['passed']} | {summary['evaluated']} | {summary['success_rate']:.3f} |"
        )

    failures = [row for row in report["rows"] if row["status"] != "passed"]
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("All evaluated front-door runs passed.")
    else:
        for row in failures[:20]:
            lines.append(
                f"- `{row['system_id']}` / `{row['source_type']}`: {row['failure_reason']}"
            )
    return "\n".join(lines) + "\n"


def write_frontdoor_benchmark_outputs(
    *,
    output_dir: str | Path = REPORTS_ROOT,
    data_dir: str | Path = DATA_ROOT,
    count: int = DEFAULT_SYNTHETIC_SYSTEM_COUNT,
    seed: int = DEFAULT_SYNTHETIC_SEED,
    tolerance: float = DEFAULT_TOLERANCE,
    run_simulink: bool = False,
    progress_callback: Callable[[int, int, dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Generate the cross-front-door benchmark dataset and reports."""
    systems = generate_synthetic_systems(count=count, seed=seed)
    payload_sets = [build_frontdoor_payloads(spec) for spec in systems]
    report = run_frontdoor_benchmark(
        systems=systems,
        tolerance=tolerance,
        run_simulink=run_simulink,
        progress_callback=progress_callback,
    )

    output_path = Path(output_dir)
    data_path = Path(data_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)

    dataset_path = data_path / "frontdoor_benchmark_systems.json"
    json_path = output_path / "frontdoor_benchmark.json"
    csv_path = output_path / "frontdoor_benchmark.csv"
    md_path = output_path / "frontdoor_benchmark.md"

    dataset_path.write_text(json.dumps([payload.to_dict() for payload in payload_sets], indent=2), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "system_id",
                "family",
                "source_type",
                "status",
                "duration_sec",
                "failure_reason",
                "state_count",
                "graph_node_count",
                "ode_rmse_vs_latex",
                "ode_max_abs_vs_latex",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {
                key: row.get(key)
                for key in writer.fieldnames
            }
            for row in report["rows"]
        )
    md_path.write_text(render_frontdoor_benchmark_markdown(report), encoding="utf-8")
    return report
