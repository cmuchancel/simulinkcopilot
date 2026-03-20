"""Export CLI pipeline runs into the Flask GUI run format."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from eqn2sim_gui.model_metadata import GuiModelMetadata, save_gui_metadata
from eqn2sim_gui.preview import render_state_trajectory_comparison_preview
from ir.equation_dict import equation_to_string
from latex_frontend.normalize import normalize_latex
from repo_paths import GUI_RUNS_ROOT


DEFAULT_GUI_REPORT_ROOT = GUI_RUNS_ROOT


def export_results_to_gui_run(
    results: Mapping[str, object],
    *,
    raw_latex: str,
    gui_report_root: str | Path | None = None,
    symbol_config: Mapping[str, str] | None = None,
    input_values: Mapping[str, float] | None = None,
) -> dict[str, str]:
    """Write a pipeline result bundle into the GUI's saved-run directory."""
    root = Path(gui_report_root or DEFAULT_GUI_REPORT_ROOT).resolve()
    artifact_dir = _artifact_dir(root, raw_latex)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    metadata = _build_gui_metadata(
        results,
        raw_latex=raw_latex,
        symbol_config=symbol_config or {},
        input_values=input_values or {},
    )

    (artifact_dir / "input_equations.tex").write_text(raw_latex, encoding="utf-8")
    metadata_path = save_gui_metadata(artifact_dir / "gui_metadata.json", metadata)
    validated_spec_path = artifact_dir / "validated_model_spec.json"
    validated_spec_path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")

    simulink_model = results.get("simulink_model")
    if simulink_model is not None:
        (artifact_dir / "simulink_model_dict.json").write_text(
            json.dumps(simulink_model, indent=2),
            encoding="utf-8",
        )

    simulink_result = results.get("simulink_result")
    if isinstance(simulink_result, Mapping) and simulink_result.get("model_file"):
        source_model = Path(str(simulink_result["model_file"])).resolve()
        if source_model.exists():
            shutil.copy2(source_model, artifact_dir / source_model.name)

    _write_state_trajectory_artifacts(results, artifact_dir)

    return {
        "run_name": artifact_dir.name,
        "artifact_dir": str(artifact_dir),
        "metadata_path": str(metadata_path.resolve()),
    }


def _artifact_dir(root: Path, latex_text: str) -> Path:
    digest = hashlib.sha1(latex_text.encode("utf-8")).hexdigest()[:12]
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    nonce = uuid.uuid4().hex[:6]
    return root / f"run_{timestamp}_{digest}_{nonce}"


def _build_gui_metadata(
    results: Mapping[str, object],
    *,
    raw_latex: str,
    symbol_config: Mapping[str, str],
    input_values: Mapping[str, float],
) -> GuiModelMetadata:
    extraction = results["extraction"]
    runtime = results["runtime"]
    parameter_values = dict(runtime["parameter_values"])  # type: ignore[index]
    initial_conditions = dict(runtime["initial_conditions"])  # type: ignore[index]

    symbols: dict[str, dict[str, Any]] = {}
    for state_name in extraction.states:  # type: ignore[attr-defined]
        if state_name.endswith("_dot"):
            continue
        symbols[state_name] = {
            "role": "state",
            "description": "",
            "units": "",
            "value": None,
            "input_kind": "constant",
        }

    for name in extraction.parameters:  # type: ignore[attr-defined]
        symbols[name] = {
            "role": "known_constant" if symbol_config.get(name) == "known_constant" else "parameter",
            "description": "",
            "units": "",
            "value": parameter_values.get(name),
            "input_kind": "constant",
        }

    for name in extraction.inputs:  # type: ignore[attr-defined]
        symbols[name] = {
            "role": "input",
            "description": "",
            "units": "",
            "value": input_values.get(name),
            "input_kind": "constant" if name in input_values else "inport",
        }

    return GuiModelMetadata(
        latex=raw_latex,
        normalized_latex=normalize_latex(raw_latex),
        equations=[equation_to_string(equation) for equation in results["equations"]],  # type: ignore[index]
        symbols=dict(sorted(symbols.items())),
        initial_conditions={str(name): float(value) for name, value in initial_conditions.items()},
        extracted_states=list(extraction.states),  # type: ignore[attr-defined]
        derivative_orders=dict(extraction.derivative_orders),  # type: ignore[attr-defined]
    )


def _write_state_trajectory_artifacts(results: Mapping[str, object], artifact_dir: Path) -> None:
    ode_result = results.get("ode_result")
    if not isinstance(ode_result, Mapping):
        return

    series_results: list[tuple[str, Mapping[str, object], str]] = [("ODE", ode_result, "-")]
    simulink_result = results.get("simulink_result")
    simulink_error = None
    if isinstance(simulink_result, Mapping) and simulink_result.get("t") is not None:
        series_results.append(("Simulink", simulink_result, "--"))
    elif results.get("simulink_validation") is None and results.get("simulink_result") is not None:
        simulink_error = "Simulink result was not available for GUI export."

    plot_result = render_state_trajectory_comparison_preview(list(series_results))
    plot_path = artifact_dir / "state_trajectory_plot.svg"
    if plot_result.svg:
        plot_path.write_text(plot_result.svg, encoding="utf-8")

    reference_result = series_results[0][1]
    time_values = [float(value) for value in reference_result["t"].tolist()]  # type: ignore[index]
    state_names = list(reference_result["state_names"])  # type: ignore[index]
    data_payload = {
        "source": "comparison",
        "t_span": [float(time_values[0]), float(time_values[-1])] if time_values else [0.0, 0.0],
        "state_names": state_names,
        "series": [
            {
                "label": label,
                "t": [float(value) for value in result["t"].tolist()],  # type: ignore[index]
                "states": {
                    state_name: [float(row[index]) for row in result["states"].tolist()]  # type: ignore[index]
                    for index, state_name in enumerate(state_names)
                },
            }
            for label, result, _style in series_results
        ],
        "simulink_error": simulink_error,
    }
    (artifact_dir / "state_trajectory_data.json").write_text(
        json.dumps(data_payload, indent=2),
        encoding="utf-8",
    )
