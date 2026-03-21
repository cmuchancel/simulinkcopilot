from __future__ import annotations

import io
import json
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from latex_frontend.symbols import DeterministicCompileError
from pipeline import run_pipeline as pipeline_module
from simulate.input_sources import detect_constant_input_values, sample_input_signals


def _write_equations(tmp_path: Path, equations: str) -> Path:
    path = tmp_path / "system.tex"
    path.write_text(equations, encoding="utf-8")
    return path


def _real_results(tmp_path: Path) -> dict[str, object]:
    path = _write_equations(tmp_path, r"\dot{x}=-ax")
    return pipeline_module.run_pipeline(
        path,
        run_sim=True,
        run_simulink=False,
        runtime_override={
            "parameter_values": {"a": 0.5},
            "initial_conditions": {"x": 1.0},
            "t_span": [0.0, 1.0],
            "sample_count": 5,
        },
    )


def _fake_results(*, with_comparison: bool = False, with_simulink: bool = False) -> dict[str, object]:
    extraction = SimpleNamespace(
        states=("x",),
        inputs=(),
        parameters=("a",),
        to_dict=lambda: {"states": ["x"], "inputs": [], "parameters": ["a"]},
    )
    dae_system = SimpleNamespace(
        to_dict=lambda: {
            "differential_states": ["x"],
            "algebraic_variables": [],
            "differential_equations": ["D1_x = x"],
            "algebraic_constraints": [],
            "solved_algebraic_variables": {},
            "residual_constraints": [],
            "reduced_equations": ["D1_x = x"],
            "reduced_to_explicit": True,
        }
    )
    consistent_initialization = SimpleNamespace(
        to_dict=lambda: {
            "differential_initial_conditions": {"x": 0.0},
            "algebraic_initial_conditions": {},
            "reduced_to_explicit": True,
        }
    )
    return {
        "source_path": "/tmp/inline_equations.tex",
        "equations": [],
        "equation_dicts": [],
        "extraction": extraction,
        "solved_derivatives": [],
        "dae_system": dae_system,
        "descriptor_system": None,
        "consistent_initialization": consistent_initialization,
        "first_order": {"states": ["x"], "inputs": [], "state_equations": [{"state": "x", "rhs": {"op": "symbol", "name": "x"}}]},
        "explicit_form": {"form": "explicit_first_order", "rhs": {"x": 1}},
        "linearity": {"is_linear": False, "offending_entries": []},
        "state_space": None,
        "graph": {"nodes": [{"id": "n1", "op": "constant"}], "edges": []},
        "ode_result": None,
        "state_space_result": None,
        "comparison": {"passes": True, "rmse": 0.0, "max_abs_error": 0.0, "tolerance": 1e-6} if with_comparison else None,
        "simulink_model": None,
        "simulink_result": {"model_name": "demo_model", "model_file": "/tmp/demo.slx"} if with_simulink else None,
        "simulink_validation": {
            "passes": True,
            "vs_ode": {"rmse": 0.0, "max_abs_error": 0.0},
            "vs_state_space": None,
        } if with_simulink else None,
        "runtime": {
            "parameter_values": {"a": 1.0},
            "initial_conditions": {"x": 0.0},
            "input_function": lambda _time: {},
            "t_span": (0.0, 1.0),
            "t_eval": np.array([0.0, 1.0]),
            "expected_linear": False,
        },
    }


def test_apply_runtime_override_validates_keys_and_sampling() -> None:
    runtime = {
        "parameter_values": {"a": 1.0},
        "initial_conditions": {"x": 0.0},
        "input_function": lambda _time: {"u": 1.0},
        "t_span": (0.0, 2.0),
        "t_eval": np.array([0.0, 1.0, 2.0]),
        "expected_linear": True,
    }

    merged = pipeline_module.apply_runtime_override(
        runtime,
        {
            "parameter_values": {"a": 2.0},
            "initial_conditions": {"x": 1.0},
            "input_values": {"u": 3.0},
            "t_span": [0.0, 4.0],
            "sample_count": 5,
            "expected_linear": False,
        },
    )
    assert merged["parameter_values"]["a"] == 2.0
    assert merged["initial_conditions"]["x"] == 1.0
    assert merged["input_function"](0.5) == {"u": 3.0}
    assert tuple(merged["t_span"]) == (0.0, 4.0)
    assert len(merged["t_eval"]) == 5
    assert merged["expected_linear"] is False

    override_with_t_eval = pipeline_module.apply_runtime_override(runtime, {"t_eval": [1.0, 2.0, 4.0]})
    assert tuple(override_with_t_eval["t_span"]) == (1.0, 4.0)
    assert override_with_t_eval["t_eval"].tolist() == [1.0, 2.0, 4.0]

    with pytest.raises(DeterministicCompileError, match="Unsupported runtime override keys"):
        pipeline_module.apply_runtime_override(runtime, {"bad_key": 1})
    with pytest.raises(DeterministicCompileError, match="t_eval must be a 1D array"):
        pipeline_module.apply_runtime_override(runtime, {"t_eval": [1.0]})
    with pytest.raises(DeterministicCompileError, match="t_span must be a two-item list or tuple"):
        pipeline_module.apply_runtime_override(runtime, {"t_span": [0.0]})
    with pytest.raises(DeterministicCompileError, match="sample_count must be at least 2"):
        pipeline_module.apply_runtime_override(runtime, {"sample_count": 1})


def test_assignment_helpers_and_state_validation() -> None:
    parse_float = pipeline_module._parse_assignment("--parameter")
    assert parse_float("m=2.5") == ("m", 2.5)
    parse_role = pipeline_module._parse_assignment("--symbol-role", value_type=str, allowed_values={"input", "parameter"})
    assert parse_role("u=input") == ("u", "input")

    for raw in ["missing", "=1", "x=", "x=abc"]:
        with pytest.raises(Exception):
            parse_float(raw)
    with pytest.raises(Exception):
        parse_role("u=state")

    merged = pipeline_module._merge_assignment_group(None, "parameter_values", [("m", 1.0), ("k", 2.0)])
    assert merged == {"parameter_values": {"m": 1.0, "k": 2.0}}

    pipeline_module._validate_expected_states(("x", "x_dot"), ["x", "x_dot", "x"])
    with pytest.raises(DeterministicCompileError, match="CLI-declared states do not match"):
        pipeline_module._validate_expected_states(("x",), ["y"])


def test_shared_input_source_helpers_cover_constant_and_nonconstant_cases() -> None:
    input_function = lambda t: {"u": 2.0 if t < 10 else 2.0}
    assert detect_constant_input_values(input_function, [], t_span=(0.0, 2.0)) == {}
    assert detect_constant_input_values(input_function, ["u"], t_span=(0.0, 2.0)) == {"u": 2.0}

    varying_input = lambda t: {"u": float(t)}
    assert detect_constant_input_values(varying_input, ["u"], t_span=(0.0, 2.0)) is None

    samples = sample_input_signals(varying_input, ["u"], np.array([0.0, 1.0, 2.0]))
    assert samples == {
        "u": {"time": [0.0, 1.0, 2.0], "values": [0.0, 1.0, 2.0]},
    }


def test_summarize_pipeline_results_and_print_cover_reporting(tmp_path: Path) -> None:
    results = _real_results(tmp_path)
    summary = pipeline_module.summarize_pipeline_results(results)

    assert summary["source_path"].endswith("system.tex")
    assert summary["extraction"]["states"] == ["x"]
    assert summary["graph"]["node_count"] >= 1
    assert summary["runtime"]["parameter_values"]["a"] == 0.5

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        pipeline_module._print_results(
            results,
            show_ir=True,
            show_first_order=True,
            show_state_space=True,
            show_graph_validation=True,
        )
    output = buffer.getvalue()
    assert "Parsed equations:" in output
    assert "Canonical equation dicts:" in output
    assert "First-order system:" in output
    assert "State-space matrices:" in output
    assert "Graph validation:" in output
    assert "Simulink backend:" in output


def test_main_rejects_invalid_cli_combinations(monkeypatch) -> None:
    invalid_argv_sets = [
        ["run_pipeline.py", "--equations", r"\dot{x}=0", "--sample-count", "1"],
        ["run_pipeline.py", "--equations", r"\dot{x}=0", "--skip-sim"],
        ["run_pipeline.py", "--equations", r"\dot{x}=0", "--no-simulink", "--export-gui-run"],
        ["run_pipeline.py", "--equations", r"\dot{x}=0", "--classification-mode", "strict", "--symbol-role", "u=input"],
    ]

    for argv in invalid_argv_sets:
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            pipeline_module.main()


def test_main_writes_report_and_verbose_bundle(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    graph_path = tmp_path / "graph.json"
    verbose_dir = tmp_path / "verbose"
    fake_verbose_module = types.SimpleNamespace(
        write_verbose_artifacts=lambda results, output_dir, matlab_engine=None: {
            "output_dir": str(output_dir),
            "files": {"walkthrough": str(Path(output_dir) / "walkthrough.md"), "other": None},
        }
    )
    monkeypatch.setitem(sys.modules, "pipeline.verbose_artifacts", fake_verbose_module)
    monkeypatch.setattr(pipeline_module, "run_pipeline", lambda *args, **kwargs: _fake_results(with_comparison=False))
    monkeypatch.setattr(pipeline_module, "_print_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_module, "summarize_pipeline_results", lambda results: {"ok": True})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--equations",
            r"\dot{x}=0",
            "--no-simulink",
            "--skip-sim",
            "--verbose",
            "--verbose-output-dir",
            str(verbose_dir),
            "--write-graph-json",
            str(graph_path),
            "--report-json",
            str(report_path),
        ],
    )

    exit_code = pipeline_module.main()

    assert exit_code == 0
    assert json.loads(report_path.read_text(encoding="utf-8")) == {"ok": True}
    assert json.loads(graph_path.read_text(encoding="utf-8")) == {"nodes": [{"id": "n1", "op": "constant"}], "edges": []}


def test_main_exports_gui_run_and_returns_simulink_status(monkeypatch, tmp_path: Path) -> None:
    export_calls: list[dict[str, object]] = []
    monkeypatch.setattr(pipeline_module, "run_pipeline", lambda *args, **kwargs: _fake_results(with_simulink=True))
    monkeypatch.setattr(pipeline_module, "_print_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pipeline_module,
        "export_results_to_gui_run",
        lambda results, raw_latex, gui_report_root, symbol_config, input_values: export_calls.append(
            {
                "raw_latex": raw_latex,
                "gui_report_root": gui_report_root,
                "symbol_config": symbol_config,
                "input_values": input_values,
            }
        ) or {
            "run_name": "run_demo",
            "artifact_dir": str(tmp_path / "run_demo"),
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--equations",
            r"\dot{x}=0",
            "--export-gui-run",
            "--gui-report-root",
            str(tmp_path / "gui_runs"),
        ],
    )

    exit_code = pipeline_module.main()

    assert exit_code == 0
    assert export_calls[0]["raw_latex"] == r"\dot{x}=0"
    assert export_calls[0]["gui_report_root"] == str(tmp_path / "gui_runs")
