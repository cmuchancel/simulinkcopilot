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

from backend.simulate_simulink import SimulinkExecutionResult
from latex_frontend.symbols import DeterministicCompileError
from pipeline import run_pipeline as pipeline_module
from pipeline.input_frontends import normalize_problem
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


def _fake_problem(*, source_type: str = "latex", name: str = "system", equations=None):
    equation_nodes = list(equations or [])
    return SimpleNamespace(
        source_type=source_type,
        source_name=lambda: name,
        source_label=lambda: f"/tmp/{name}.tex",
        equation_nodes=lambda: equation_nodes,
        declared_symbol_config=lambda: {},
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
        "dae_classification": {
            "kind": "explicit_ode",
            "route": "explicit_ode",
            "supported": True,
            "python_validation_supported": True,
            "simulink_lowering_supported": True,
            "diagnostic": None,
        },
        "equations": [],
        "equation_dicts": [],
        "extraction": extraction,
        "solved_derivatives": [],
        "dae_system": dae_system,
        "dae_validation": None,
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


def _descriptor_like_results() -> dict[str, object]:
    result = _fake_results(with_simulink=True)
    result["dae_classification"] = {
        "kind": "linear_descriptor_dae",
        "route": "descriptor_dae",
        "supported": True,
        "python_validation_supported": True,
        "simulink_lowering_supported": True,
        "diagnostic": None,
    }
    result["dae_validation"] = None
    result["first_order"] = None
    result["graph"] = None
    result["descriptor_system"] = None
    result["comparison"] = None
    result["simulink_validation"] = {
        "passes": True,
        "vs_dae_python": {"rmse": 0.0, "max_abs_error": 0.0},
    }
    return result


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


def test_simulink_subset_result_extracts_named_columns() -> None:
    subset = pipeline_module._simulink_subset_result(
        {
            "t": [0.0, 1.0],
            "signals": {
                "x": [1.0, 0.5],
                "y": [2.0, 1.5],
            },
        },
        ["y", "x"],
    )
    assert subset["state_names"] == ["y", "x"]
    assert subset["states"].tolist() == [[2.0, 1.0], [1.5, 0.5]]


def test_supported_dae_rejection_message_and_print_results_cover_optional_paths() -> None:
    assert pipeline_module._supported_dae_rejection_message({"kind": "unsupported_dae", "diagnostic": None}).startswith(
        "Unsupported DAE class"
    )
    assert "Diagnostic: ill posed" in pipeline_module._supported_dae_rejection_message(
        {"kind": "unsupported_dae", "diagnostic": "ill posed"}
    )

    default_validation = _fake_results(with_simulink=True)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        pipeline_module._print_results(
            default_validation,
            show_ir=False,
            show_first_order=False,
            show_state_space=False,
            show_graph_validation=False,
        )
    assert "vs_ode_rmse: 0.0" in buffer.getvalue()

    unavailable_validation = _fake_results(with_simulink=True) | {"simulink_validation": None}
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        pipeline_module._print_results(
            unavailable_validation,
            show_ir=False,
            show_first_order=False,
            show_state_space=False,
            show_graph_validation=False,
        )
    assert "validation: unavailable" in buffer.getvalue()

    state_space_validation = _fake_results(with_simulink=True)
    state_space_validation["simulink_validation"] = {
        "passes": True,
        "vs_ode": {"rmse": 0.0, "max_abs_error": 0.0},
        "vs_state_space": {"rmse": 1.0, "max_abs_error": 2.0},
    }
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        pipeline_module._print_results(
            state_space_validation,
            show_ir=False,
            show_first_order=False,
            show_state_space=False,
            show_graph_validation=False,
        )
    output = buffer.getvalue()
    assert "vs_state_space_rmse: 1.0" in output
    assert "vs_state_space_max_abs_error: 2.0" in output


def test_print_results_covers_descriptor_and_simulink_validation_paths() -> None:
    results = _descriptor_like_results()
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        pipeline_module._print_results(
            results,
            show_ir=False,
            show_first_order=False,
            show_state_space=False,
            show_graph_validation=False,
        )
    output = buffer.getvalue()
    assert "unavailable: descriptor-only Simulink path" in output
    assert "vs_dae_python_rmse: 0.0" in output
    assert "model_name: demo_model" in output


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

    monkeypatch.setattr(sys, "argv", ["run_pipeline.py"])
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


def test_main_runtime_json_expected_linear_and_failed_return_paths(monkeypatch, tmp_path: Path) -> None:
    runtime_path = tmp_path / "runtime.json"
    report_path = tmp_path / "report.json"
    runtime_path.write_text(json.dumps({"parameter_values": {"a": 2.0}}), encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run_pipeline(*args, **kwargs):
        captured["runtime_override"] = kwargs["runtime_override"]
        return _fake_results(with_comparison=True)

    monkeypatch.setattr(pipeline_module, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        pipeline_module,
        "_print_results",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        pipeline_module,
        "summarize_pipeline_results",
        lambda results: {"ok": True},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--equations",
            r"\dot{x}=0",
            "--no-simulink",
            "--runtime-json",
            str(runtime_path),
            "--expected-linear",
            "--report-json",
            str(report_path),
        ],
    )

    exit_code = pipeline_module.main()
    assert exit_code == 0
    assert captured["runtime_override"]["parameter_values"]["a"] == 2.0
    assert captured["runtime_override"]["expected_linear"] is True

    monkeypatch.setattr(pipeline_module, "run_pipeline", lambda *args, **kwargs: _fake_results(with_comparison=False, with_simulink=True) | {"simulink_validation": {"passes": False}})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--equations",
            r"\dot{x}=0",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 1

    failing_compare = _fake_results(with_comparison=True)
    failing_compare["comparison"]["passes"] = False
    monkeypatch.setattr(pipeline_module, "run_pipeline", lambda *args, **kwargs: failing_compare)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--equations",
            r"\dot{x}=0",
            "--no-simulink",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 1


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


def test_main_handles_nonlatex_input_and_verbose_simulink_engine(monkeypatch, tmp_path: Path) -> None:
    equations_path = tmp_path / "system.txt"
    equations_path.write_text("diff(x,t) == -x", encoding="utf-8")
    report_path = tmp_path / "report.json"
    start_calls: list[dict[str, object]] = []
    engine = SimpleNamespace(quit=lambda: start_calls.append({"quit": True}))

    fake_engine_module = types.SimpleNamespace(
        start_engine=lambda **kwargs: start_calls.append(kwargs) or engine
    )
    fake_verbose_module = types.SimpleNamespace(
        write_verbose_artifacts=lambda results, output_dir, matlab_engine=None: {
            "output_dir": str(output_dir),
            "files": {},
        }
    )
    monkeypatch.setitem(sys.modules, "simulink.engine", fake_engine_module)
    monkeypatch.setitem(sys.modules, "pipeline.verbose_artifacts", fake_verbose_module)
    monkeypatch.setattr(
        pipeline_module,
        "run_pipeline_problem",
        lambda problem, **kwargs: _fake_results(with_comparison=False) | {"source_type": problem.source_type},
    )
    monkeypatch.setattr(pipeline_module, "_print_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_module, "summarize_pipeline_results", lambda results: {"ok": True})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input",
            str(equations_path),
            "--source-type",
            "matlab_symbolic",
            "--no-simulink",
            "--skip-sim",
            "--verbose",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input",
            str(equations_path),
            "--source-type",
            "matlab_symbolic",
            "--skip-sim",
            "--verbose",
            "--report-json",
            str(report_path),
        ],
    )
    with pytest.raises(SystemExit):
        pipeline_module.main()

    latex_path = tmp_path / "system.tex"
    latex_path.write_text(r"\dot{x}=0", encoding="utf-8")
    monkeypatch.setattr(
        pipeline_module,
        "run_pipeline",
        lambda *args, **kwargs: _fake_results(with_simulink=True),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input",
            str(latex_path),
            "--verbose",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 0
    assert any(call.get("retries") == 1 for call in start_calls if isinstance(call, dict))
    assert {"quit": True} in start_calls


def test_main_covers_payload_normalization_and_input_file_gui_export_paths(monkeypatch, tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    report_path = tmp_path / "report.json"
    payload_path.write_text(json.dumps({"source_type": "matlab_symbolic", "equations": ["diff(x,t) == -x"]}), encoding="utf-8")
    monkeypatch.setattr(pipeline_module, "run_pipeline_problem", lambda problem, **kwargs: _fake_results() | {"source_type": problem.source_type})
    monkeypatch.setattr(pipeline_module, "_print_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_module, "summarize_pipeline_results", lambda results: {"ok": True})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input-payload-json",
            str(payload_path),
            "--no-simulink",
            "--skip-sim",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 0

    bad_payload_path = tmp_path / "bad_payload.json"
    bad_payload_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input-payload-json",
            str(bad_payload_path),
        ],
    )
    with pytest.raises(SystemExit):
        pipeline_module.main()

    injected_payload_path = tmp_path / "injected_payload.json"
    injected_payload_path.write_text(json.dumps({"equations": ["xdot = -x"], "states": ["x"]}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input-payload-json",
            str(injected_payload_path),
            "--source-type",
            "matlab_equation_text",
            "--no-simulink",
            "--skip-sim",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--equations",
            "diff(x,t) == -x",
            "--source-type",
            "matlab_symbolic",
            "--no-simulink",
            "--skip-sim",
            "--report-json",
            str(report_path),
        ],
    )
    assert pipeline_module.main() == 0

    latex_path = tmp_path / "system.tex"
    latex_path.write_text(r"\dot{x}=0", encoding="utf-8")
    export_calls: list[str] = []
    monkeypatch.setattr(pipeline_module, "run_pipeline", lambda *args, **kwargs: _fake_results(with_simulink=True))
    monkeypatch.setattr(
        pipeline_module,
        "export_results_to_gui_run",
        lambda results, raw_latex, gui_report_root, symbol_config, input_values: export_calls.append(raw_latex) or {
            "run_name": "demo",
            "artifact_dir": str(tmp_path / "demo"),
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input",
            str(latex_path),
            "--export-gui-run",
        ],
    )
    assert pipeline_module.main() == 0
    assert export_calls == [r"\dot{x}=0"]


def test_run_pipeline_problem_reuses_external_matlab_engine_without_quitting(monkeypatch) -> None:
    quit_calls: list[bool] = []
    engine = SimpleNamespace(quit=lambda: quit_calls.append(True))
    problem = normalize_problem(
        {
            "source_type": "latex",
            "text": r"\dot{x}=-x",
            "states": ["x"],
        }
    )

    monkeypatch.setattr(
        "backend.simulate_simulink.execute_simulink_graph",
        lambda *args, **kwargs: SimulinkExecutionResult(
            model={"blocks": {"b1": {}}},
            simulation={"model_name": "demo_model", "model_file": "demo.slx", "signals": {"x": [0.0, 0.0]}, "t": [0.0, 1.0]},
            validation={"passes": True, "vs_ode": {"rmse": 0.0, "max_abs_error": 0.0}, "vs_state_space": None},
            build_time_sec=0.1,
            simulation_time_sec=0.2,
        ),
    )

    result = pipeline_module.run_pipeline_problem(
        problem,
        run_sim=True,
        run_simulink=True,
        runtime_override={
            "initial_conditions": {"x": 1.0},
            "t_span": [0.0, 1.0],
            "sample_count": 5,
        },
        matlab_engine=engine,
    )

    assert result["simulink_validation"]["passes"] is True
    assert quit_calls == []


def test_run_pipeline_falls_back_to_descriptor_simulink_for_nonreduced_dae(monkeypatch, tmp_path: Path) -> None:
    path = _write_equations(tmp_path, "\\dot{x}+y=u\nx+y=1")
    extraction = SimpleNamespace(
        states=("x",),
        inputs=("u",),
        parameters=(),
        independent_variable=None,
        to_dict=lambda: {"states": ["x"], "inputs": ["u"], "parameters": []},
    )
    dae_system = SimpleNamespace(
        differential_states=("x",),
        algebraic_variables=("y",),
        reduced_to_explicit=False,
        classification=SimpleNamespace(
            to_dict=lambda: {
                "kind": "linear_descriptor_dae",
                "route": "descriptor_dae",
                "supported": True,
                "python_validation_supported": True,
                "simulink_lowering_supported": True,
                "diagnostic": None,
            }
        ),
        to_dict=lambda: {
            "differential_states": ["x"],
            "algebraic_variables": ["y"],
            "differential_equations": [],
            "algebraic_constraints": [],
            "solved_algebraic_variables": {},
            "residual_constraints": ["x + y = 1"],
            "reduced_equations": [],
            "reduced_to_explicit": False,
        },
    )
    analysis = SimpleNamespace(
        extraction=extraction,
        resolved_equations=[],
        solved_derivatives=None,
        dae_reduction=None,
        dae_system=dae_system,
        descriptor_system={"form": "linear_descriptor"},
    )
    descriptor_compilation = SimpleNamespace(
        equation_dicts=[],
        extraction=extraction,
        dae_system=dae_system,
        descriptor_system={
            "form": "linear_descriptor",
            "variables": ["x", "y"],
            "differential_states": ["x"],
            "algebraic_variables": ["y"],
        },
    )

    monkeypatch.setattr(pipeline_module, "analyze_state_extraction", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(
        pipeline_module,
        "compile_descriptor_system_from_analysis",
        lambda *args, **kwargs: descriptor_compilation,
    )
    monkeypatch.setattr(
        pipeline_module,
        "initialize_preserved_dae",
        lambda *args, **kwargs: SimpleNamespace(
            differential_initial_conditions={"x": 1.0},
            algebraic_initial_conditions={"y": 0.0},
        ),
    )

    fake_backend_module = types.SimpleNamespace(
        execute_simulink_descriptor=lambda *args, **kwargs: SimpleNamespace(
            model={"blocks": {"alg": {}}, "outputs": [{"name": "x"}, {"name": "y"}]},
            simulation={"model_name": "dae_model", "model_file": "/tmp/dae_model.slx"},
            validation=None,
        ),
        execute_simulink_graph=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("graph path should not run")),
        execute_simulink_preserved_dae_graph=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("preserved DAE graph path should not run")
        ),
    )
    fake_engine_module = types.SimpleNamespace(start_engine=lambda **kwargs: SimpleNamespace(quit=lambda: None))
    monkeypatch.setitem(sys.modules, "backend.simulate_simulink", fake_backend_module)
    monkeypatch.setitem(sys.modules, "simulink.engine", fake_engine_module)

    result = pipeline_module.run_pipeline(
        path,
        run_sim=False,
        run_simulink=True,
        runtime_override={
            "initial_conditions": {"x": 1.0, "y": 0.0},
            "input_values": {"u": 0.5},
            "t_span": [0.0, 1.0],
            "sample_count": 5,
        },
    )

    assert result["first_order"] is None
    assert result["graph"] is None
    assert result["simulink_result"]["model_name"] == "dae_model"
    assert result["simulink_validation"] is None
    assert result["consistent_initialization"].algebraic_initial_conditions == {"y": 0.0}


def test_run_pipeline_preserved_dae_builds_python_comparison_when_backend_validation_missing(monkeypatch) -> None:
    extraction = SimpleNamespace(states=("x",), inputs=(), parameters=(), independent_variable=None)
    dae_system = SimpleNamespace(
        differential_states=("x",),
        algebraic_variables=("z",),
        reduced_to_explicit=False,
        classification=SimpleNamespace(
            to_dict=lambda: {
                "kind": "nonlinear_preserved_semi_explicit_dae",
                "route": "preserved_dae",
                "supported": True,
                "python_validation_supported": True,
                "simulink_lowering_supported": True,
                "diagnostic": None,
            }
        ),
    )
    analysis = SimpleNamespace(dae_system=dae_system)
    preserved_compilation = SimpleNamespace(
        extraction=extraction,
        dae_system=dae_system,
        equation_dicts=[],
        graph={"nodes": [{"id": "n1", "op": "constant", "inputs": []}], "edges": []},
        validated_graph={"nodes": [{"id": "n1", "op": "constant", "inputs": []}], "edges": []},
    )
    problem = _fake_problem()

    monkeypatch.setattr(pipeline_module, "_analyze_problem", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(
        pipeline_module,
        "compile_preserved_dae_system_from_analysis",
        lambda *args, **kwargs: preserved_compilation,
    )
    monkeypatch.setattr(
        pipeline_module,
        "initialize_preserved_dae",
        lambda *args, **kwargs: SimpleNamespace(
            differential_initial_conditions={"x": 1.0},
            algebraic_initial_conditions={"z": 0.2},
        ),
    )
    monkeypatch.setattr(
        pipeline_module,
        "validate_preserved_semi_explicit_dae",
        lambda *args, **kwargs: SimpleNamespace(
            to_dict=lambda: {
                "t": [0.0, 1.0],
                "differential_states": [[1.0], [0.5]],
                "simulation_success": True,
                "residual_norm_max": 0.0,
                "residual_norm_final": 0.0,
            }
        ),
    )
    fake_backend_module = types.SimpleNamespace(
        execute_simulink_descriptor=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("descriptor path should not run")),
        execute_simulink_graph=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("graph path should not run")),
        execute_simulink_preserved_dae_graph=lambda *args, **kwargs: SimpleNamespace(
            model={"blocks": {}},
            simulation={"model_name": "dae_model", "model_file": "/tmp/dae_model.slx", "t": [0.0, 1.0], "signals": {"x": [1.0, 0.5], "z": [0.2, 0.1]}},
            validation=None,
        ),
    )
    fake_engine_module = types.SimpleNamespace(start_engine=lambda **kwargs: SimpleNamespace(quit=lambda: None))
    monkeypatch.setitem(sys.modules, "backend.simulate_simulink", fake_backend_module)
    monkeypatch.setitem(sys.modules, "simulink.engine", fake_engine_module)

    result = pipeline_module._run_normalized_problem(problem, run_sim=True, run_simulink=True)

    assert result["simulink_validation"]["passes"] is True
    assert result["simulink_validation"]["vs_dae_python"]["rmse"] == 0.0


def test_run_pipeline_explicit_graph_requires_backend_validation(monkeypatch) -> None:
    extraction = SimpleNamespace(states=("x",), inputs=(), parameters=(), independent_variable=None)
    dae_system = SimpleNamespace(
        differential_states=("x",),
        algebraic_variables=(),
        reduced_to_explicit=True,
        classification=SimpleNamespace(
            to_dict=lambda: {
                "kind": "explicit_ode",
                "route": "explicit_ode",
                "supported": True,
                "python_validation_supported": True,
                "simulink_lowering_supported": True,
                "diagnostic": None,
            }
        ),
    )
    analysis = SimpleNamespace(dae_system=dae_system)
    compilation = SimpleNamespace(
        extraction=extraction,
        solved_derivatives=[],
        dae_system=dae_system,
        descriptor_system=None,
        first_order={"states": ["x"], "inputs": [], "parameters": [], "state_equations": []},
        explicit_form={},
        linearity={"is_linear": False, "offending_entries": []},
        state_space=None,
        graph={"nodes": [{"id": "n1", "op": "constant", "inputs": []}], "edges": []},
        validated_graph={"nodes": [{"id": "n1", "op": "constant", "inputs": []}], "edges": []},
        equation_dicts=[],
    )
    problem = _fake_problem()

    monkeypatch.setattr(pipeline_module, "_analyze_problem", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(
        pipeline_module,
        "compile_symbolic_system_from_analysis",
        lambda *args, **kwargs: compilation,
    )
    monkeypatch.setattr(
        pipeline_module,
        "consistent_initialize_dae",
        lambda *args, **kwargs: SimpleNamespace(
            differential_initial_conditions={"x": 0.0},
            algebraic_initial_conditions={},
            to_dict=lambda: {"differential_initial_conditions": {"x": 0.0}, "algebraic_initial_conditions": {}, "reduced_to_explicit": True},
        ),
    )
    monkeypatch.setattr(
        pipeline_module,
        "simulate_ode_system",
        lambda *args, **kwargs: {"t": [0.0, 1.0], "states": np.array([[0.0], [0.0]])},
    )
    monkeypatch.setattr(
        pipeline_module,
        "default_runtime_context",
        lambda stem, first_order_system: {
            "parameter_values": {},
            "initial_conditions": {"x": 0.0},
            "input_function": lambda _time: {},
            "t_span": (0.0, 1.0),
            "t_eval": np.array([0.0, 1.0]),
            "expected_linear": False,
        },
    )
    fake_backend_module = types.SimpleNamespace(
        execute_simulink_descriptor=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("descriptor path should not run")),
        execute_simulink_graph=lambda *args, **kwargs: SimpleNamespace(
            model={"blocks": {}},
            simulation={"model_name": "ode_model", "model_file": "/tmp/ode_model.slx"},
            validation=None,
        ),
        execute_simulink_preserved_dae_graph=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("preserved path should not run")),
    )
    fake_engine_module = types.SimpleNamespace(start_engine=lambda **kwargs: SimpleNamespace(quit=lambda: None))
    monkeypatch.setitem(sys.modules, "backend.simulate_simulink", fake_backend_module)
    monkeypatch.setitem(sys.modules, "simulink.engine", fake_engine_module)

    with pytest.raises(DeterministicCompileError, match="Simulink validation requires the direct ODE simulation result"):
        pipeline_module._run_normalized_problem(problem, run_sim=True, run_simulink=True)


def test_main_accepts_matlab_symbolic_payload_json(tmp_path: Path, monkeypatch) -> None:
    payload_path = tmp_path / "payload.json"
    report_path = tmp_path / "report.json"
    payload_path.write_text(
        json.dumps(
            {
                "source_type": "matlab_symbolic",
                "equations": ["diff(x,t) == -x + u"],
                "states": ["x"],
                "inputs": ["u"],
                "time_variable": "t",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input-payload-json",
            str(payload_path),
            "--no-simulink",
            "--skip-sim",
            "--report-json",
            str(report_path),
        ],
    )

    exit_code = pipeline_module.main()
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["source_type"] == "matlab_symbolic"
    assert report["normalized_problem"]["source_type"] == "matlab_symbolic"
    assert report["dae_classification"]["kind"] == "explicit_ode"


def test_main_request_mode_rejects_conflicting_flags(monkeypatch) -> None:
    invalid_argv_sets = [
        ["run_pipeline.py", "--request", "req.json", "--input", "system.tex", "--response", "resp.json"],
        ["run_pipeline.py", "--request", "req.json", "--equations", r"\dot{x}=0", "--response", "resp.json"],
        ["run_pipeline.py", "--request", "req.json", "--input-payload-json", "payload.json", "--response", "resp.json"],
        ["run_pipeline.py", "--request", "req.json", "--response", "resp.json", "--export-gui-run"],
    ]

    for argv in invalid_argv_sets:
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            pipeline_module.main()


def test_main_rejects_payload_source_type_conflicts_and_missing_source_type(tmp_path: Path, monkeypatch) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"equations": ["xdot = -x"]}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["run_pipeline.py", "--input-payload-json", str(payload_path), "--no-simulink", "--skip-sim"],
    )
    with pytest.raises(SystemExit):
        pipeline_module.main()

    payload_path.write_text(
        json.dumps({"source_type": "matlab_symbolic", "equations": ["diff(x,t) == -x"], "states": ["x"], "time_variable": "t"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input-payload-json",
            str(payload_path),
            "--source-type",
            "latex",
            "--no-simulink",
            "--skip-sim",
        ],
    )
    with pytest.raises(SystemExit):
        pipeline_module.main()


def test_main_rejects_matlab_ode_function_without_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_pipeline.py", "--equations", "xdot = -x", "--source-type", "matlab_ode_function"],
    )
    with pytest.raises(SystemExit):
        pipeline_module.main()


def test_main_rejects_gui_export_for_non_latex_payload(tmp_path: Path, monkeypatch) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "source_type": "matlab_equation_text",
                "equations": ["xdot = -x"],
                "states": ["x"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--input-payload-json",
            str(payload_path),
            "--export-gui-run",
        ],
    )
    with pytest.raises(SystemExit):
        pipeline_module.main()
