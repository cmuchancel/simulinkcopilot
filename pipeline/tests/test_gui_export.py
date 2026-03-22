from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from eqn2sim_gui.preview import PreviewRenderResult
from latex_frontend.translator import translate_latex
from pipeline import gui_export as gui_export_module


def _results(tmp_path: Path) -> dict[str, object]:
    equations = translate_latex(r"\dot{x}=u+a")
    extraction = SimpleNamespace(
        states=("x", "x_dot"),
        inputs=("u", "v"),
        parameters=("a",),
        independent_variable="t",
        derivative_orders={"x": 1},
    )
    return {
        "equations": equations,
        "extraction": extraction,
        "runtime": {
            "parameter_values": {"a": 2.0},
            "initial_conditions": {"x": 1.0},
        },
        "ode_result": {
            "t": SimpleNamespace(tolist=lambda: [0.0, 1.0]),
            "state_names": ["x"],
            "states": SimpleNamespace(tolist=lambda: [[1.0], [0.5]]),
        },
        "simulink_result": {"model_file": str(tmp_path / "demo.slx")},
        "simulink_model": {"blocks": {"b1": {}}},
        "simulink_validation": None,
    }


def test_build_gui_metadata_includes_independent_variable_and_input_kinds(tmp_path: Path) -> None:
    metadata = gui_export_module._build_gui_metadata(
        _results(tmp_path),
        raw_latex=r"\dot{x}=u+a",
        symbol_config={"a": "known_constant"},
        input_values={"u": 3.0},
    )

    assert metadata.symbols["a"]["role"] == "known_constant"
    assert metadata.symbols["u"]["input_kind"] == "constant"
    assert metadata.symbols["v"]["input_kind"] == "inport"
    assert metadata.symbols["t"]["role"] == "independent_variable"


def test_build_gui_metadata_omits_independent_variable_when_absent(tmp_path: Path) -> None:
    results = _results(tmp_path)
    results["extraction"] = SimpleNamespace(
        states=("x",),
        inputs=("u",),
        parameters=("a",),
        independent_variable=None,
        derivative_orders={"x": 1},
    )

    metadata = gui_export_module._build_gui_metadata(
        results,
        raw_latex=r"\dot{x}=u+a",
        symbol_config={},
        input_values={},
    )

    assert "t" not in metadata.symbols


def test_write_state_trajectory_artifacts_handles_missing_ode_and_missing_simulink_result(monkeypatch, tmp_path: Path) -> None:
    gui_export_module._write_state_trajectory_artifacts({"ode_result": None}, tmp_path)
    assert not (tmp_path / "state_trajectory_data.json").exists()

    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg="<svg/>"),
    )
    results = _results(tmp_path)
    gui_export_module._write_state_trajectory_artifacts(results, tmp_path)

    payload = json.loads((tmp_path / "state_trajectory_data.json").read_text(encoding="utf-8"))
    assert payload["simulink_error"] == "Simulink result was not available for GUI export."
    assert (tmp_path / "state_trajectory_plot.svg").read_text(encoding="utf-8") == "<svg/>"


def test_write_state_trajectory_artifacts_includes_simulink_series_when_available(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg="<svg/>"),
    )
    results = _results(tmp_path) | {
        "simulink_result": {
            "t": SimpleNamespace(tolist=lambda: [0.0, 1.0]),
            "state_names": ["x"],
            "states": SimpleNamespace(tolist=lambda: [[1.0], [0.4]]),
        },
        "simulink_validation": {"status": "ok"},
    }
    gui_export_module._write_state_trajectory_artifacts(results, tmp_path)

    payload = json.loads((tmp_path / "state_trajectory_data.json").read_text(encoding="utf-8"))
    assert [series["label"] for series in payload["series"]] == ["ODE", "Simulink"]
    assert payload["simulink_error"] is None


def test_export_results_to_gui_run_writes_expected_artifacts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg="<svg/>"),
    )
    model_file = tmp_path / "demo.slx"
    model_file.write_text("demo", encoding="utf-8")

    export = gui_export_module.export_results_to_gui_run(
        _results(tmp_path) | {"simulink_result": {"model_file": str(model_file)}},
        raw_latex=r"\dot{x}=u+a",
        gui_report_root=tmp_path / "gui_runs",
        symbol_config={"a": "known_constant"},
        input_values={"u": 3.0},
    )

    artifact_dir = Path(export["artifact_dir"])
    assert (artifact_dir / "input_equations.tex").read_text(encoding="utf-8") == r"\dot{x}=u+a"
    assert (artifact_dir / "gui_metadata.json").exists()
    assert (artifact_dir / "validated_model_spec.json").exists()
    assert (artifact_dir / "simulink_model_dict.json").exists()
    assert (artifact_dir / "demo.slx").exists()


def test_export_results_to_gui_run_skips_optional_simulink_artifacts_when_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg="<svg/>"),
    )
    export = gui_export_module.export_results_to_gui_run(
        _results(tmp_path)
        | {
            "simulink_model": None,
            "simulink_result": "not-a-mapping",
        },
        raw_latex=r"\dot{x}=u+a",
        gui_report_root=tmp_path / "gui_runs",
    )

    artifact_dir = Path(export["artifact_dir"])
    assert not (artifact_dir / "simulink_model_dict.json").exists()
    assert not any(path.suffix == ".slx" for path in artifact_dir.iterdir())


def test_export_results_to_gui_run_skips_missing_model_file_copy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg="<svg/>"),
    )
    export = gui_export_module.export_results_to_gui_run(
        _results(tmp_path) | {"simulink_result": {"model_file": str(tmp_path / "missing.slx")}},
        raw_latex=r"\dot{x}=u+a",
        gui_report_root=tmp_path / "gui_runs",
    )

    artifact_dir = Path(export["artifact_dir"])
    assert not (artifact_dir / "missing.slx").exists()


def test_export_results_to_gui_run_skips_copy_for_falsey_model_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg="<svg/>"),
    )
    export = gui_export_module.export_results_to_gui_run(
        _results(tmp_path) | {"simulink_result": {"model_file": ""}},
        raw_latex=r"\dot{x}=u+a",
        gui_report_root=tmp_path / "gui_runs",
    )

    artifact_dir = Path(export["artifact_dir"])
    assert not any(path.suffix == ".slx" for path in artifact_dir.iterdir())


def test_write_state_trajectory_artifacts_omits_plot_and_simulink_error_when_not_applicable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gui_export_module,
        "render_state_trajectory_comparison_preview",
        lambda series_results: PreviewRenderResult(svg=""),
    )
    results = _results(tmp_path) | {
        "simulink_result": None,
        "simulink_validation": {"status": "skipped"},
    }
    gui_export_module._write_state_trajectory_artifacts(results, tmp_path)

    payload = json.loads((tmp_path / "state_trajectory_data.json").read_text(encoding="utf-8"))
    assert payload["simulink_error"] is None
    assert not (tmp_path / "state_trajectory_plot.svg").exists()
