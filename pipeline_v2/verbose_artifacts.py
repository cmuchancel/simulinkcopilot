"""Verbose artifact generation for CLI pipeline runs."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ir_v2.equation_dict import equation_to_string, expression_from_dict, expression_to_sympy, matrix_from_dict
from pipeline_v2.run_pipeline import summarize_pipeline_results


def _matlab_string_literal(value: str) -> str:
    return value.replace("'", "''")


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def _write_json(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _simulation_series(results: dict[str, object]) -> list[tuple[str, dict[str, object], str]]:
    series: list[tuple[str, dict[str, object], str]] = []
    if results["ode_result"] is not None:
        series.append(("ODE", results["ode_result"], "-"))
    if results["state_space_result"] is not None:
        series.append(("State-space", results["state_space_result"], "--"))
    if results["simulink_result"] is not None:
        series.append(("Simulink", results["simulink_result"], ":"))
    return series


def _render_simulation_plot(results: dict[str, object], output_path: Path) -> str | None:
    series = _simulation_series(results)
    if not series:
        return None

    state_names = list(series[0][1]["state_names"])  # type: ignore[index]
    state_count = len(state_names)
    columns = 1 if state_count <= 2 else 2
    rows = math.ceil(state_count / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(10, 3.5 * rows), squeeze=False)

    for index, state_name in enumerate(state_names):
        axis = axes[index // columns][index % columns]
        for label, result, style in series:
            axis.plot(
                result["t"],  # type: ignore[index]
                result["states"][:, index],  # type: ignore[index]
                style,
                linewidth=1.5,
                label=label,
            )
        axis.set_title(state_name)
        axis.set_xlabel("t")
        axis.grid(True, alpha=0.3)
        axis.legend()

    for index in range(state_count, rows * columns):
        axes[index // columns][index % columns].axis("off")

    figure.tight_layout()
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return str(output_path)


def _render_simulink_model_image(eng, model_name: str, output_path: Path) -> str:
    escaped_model = _matlab_string_literal(model_name)
    escaped_output = _matlab_string_literal(str(output_path.resolve()))
    eng.open_system(model_name, nargout=0)
    eng.eval(f"set_param('{escaped_model}', 'ZoomFactor', 'FitSystem');", nargout=0)
    eng.eval(f"print('-s{escaped_model}', '-dpng', '{escaped_output}')", nargout=0)
    return str(output_path)


def write_verbose_artifacts(
    results: dict[str, object],
    output_dir: str | Path,
    *,
    matlab_engine=None,
) -> dict[str, object]:
    """Write a verbose artifact bundle for a pipeline run."""
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    source_path = Path(str(results["source_path"]))
    parsed_equations = [equation_to_string(equation) for equation in results["equations"]]  # type: ignore[index]
    solved_derivatives = [equation_to_string(item.equation) for item in results["solved_derivatives"]]  # type: ignore[index]
    first_order_lines = [
        f"d/dt {entry['state']} = {expression_to_sympy(expression_from_dict(entry['rhs']))}"
        for entry in results["first_order"]["state_equations"]  # type: ignore[index]
    ]

    state_space = results["state_space"]
    if state_space is None:
        state_space_text = "unavailable: nonlinear explicit system\n"
    else:
        state_space_text = "\n".join(
            [
                f"A = {matrix_from_dict(state_space['A'])}",
                f"B = {matrix_from_dict(state_space['B'])}",
                f"C = {matrix_from_dict(state_space['C'])}",
                f"D = {matrix_from_dict(state_space['D'])}",
                f"offset = {matrix_from_dict(state_space['offset'])}",
            ]
        ) + "\n"

    intermediate_text = "\n".join(
        [
            "Parsed equations:",
            *[f"  {entry}" for entry in parsed_equations],
            "",
            "Solved derivatives:",
            *[f"  {entry}" for entry in solved_derivatives],
            "",
            "First-order system:",
            *[f"  {entry}" for entry in first_order_lines],
        ]
    ) + "\n"

    files: dict[str, str | None] = {}
    files["input_equations"] = _write_text(output_root / "input_equations.tex", source_path.read_text(encoding="utf-8"))
    files["parsed_equations"] = _write_text(output_root / "parsed_equations.txt", "\n".join(parsed_equations) + "\n")
    files["intermediate_equations"] = _write_text(output_root / "intermediate_equations.txt", intermediate_text)
    files["state_space"] = _write_text(output_root / "state_space.txt", state_space_text)
    files["graph"] = _write_json(output_root / "graph.json", results["graph"])
    files["summary"] = _write_json(output_root / "summary.json", summarize_pipeline_results(results))
    files["simulation_plot"] = _render_simulation_plot(results, output_root / "simulation_plot.png")

    simulink_result = results["simulink_result"]
    if simulink_result is not None and matlab_engine is not None:
        try:
            files["simulink_model_image"] = _render_simulink_model_image(
                matlab_engine,
                str(simulink_result["model_name"]),
                output_root / "simulink_model.png",
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            files["simulink_model_image"] = None
            files["simulink_model_note"] = _write_text(
                output_root / "simulink_model_note.txt",
                f"Failed to export Simulink model image: {exc}\n",
            )
    else:
        files["simulink_model_image"] = None
        files["simulink_model_note"] = _write_text(
            output_root / "simulink_model_note.txt",
            "Simulink model image unavailable because the Simulink backend was not requested.\n",
        )

    manifest = {
        "output_dir": str(output_root),
        "files": files,
    }
    _write_json(output_root / "artifact_manifest.json", manifest)
    return manifest
