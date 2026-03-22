from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

import pytest

from backend.simulate_simulink import SimulinkExecutionStageError
from canonicalize.dae_system import DaeSupportClassification
from simulate.dae_benchmark_suite import (
    DAE_BENCHMARK_CASES,
    DaeBenchmarkCase,
    _execute_supported_case,
    _lower_supported_case,
    _runtime_override,
    _time_grid,
    render_dae_benchmark_markdown,
    run_dae_benchmark,
    write_dae_benchmark_reports,
)


class DaeBenchmarkSuiteTests(unittest.TestCase):
    def test_dae_benchmark_reports_supported_and_unsupported_cases(self) -> None:
        report = run_dae_benchmark(
            selected_cases=[
                "reducible_nonlinear_helper",
                "linear_descriptor_capable_balance",
                "nonlinear_preserved_cubic_constraint",
                "unsupported_high_order_preserved_dae",
            ],
            run_simulink=False,
        )
        by_name = {entry["name"]: entry for entry in report["cases"]}
        self.assertTrue(by_name["reducible_nonlinear_helper"]["overall_pass"])
        self.assertEqual(by_name["reducible_nonlinear_helper"]["classification"]["kind"], "reducible_semi_explicit_dae")
        self.assertTrue(by_name["linear_descriptor_capable_balance"]["metrics"]["descriptor_artifact_available"])
        self.assertEqual(
            by_name["nonlinear_preserved_cubic_constraint"]["classification"]["kind"],
            "nonlinear_preserved_semi_explicit_dae",
        )
        self.assertEqual(
            by_name["unsupported_high_order_preserved_dae"]["stages"]["pipeline"]["status"],
            "expected_failure",
        )
        self.assertTrue(by_name["unsupported_high_order_preserved_dae"]["overall_pass"])

    def test_dae_benchmark_markdown_contains_case_names(self) -> None:
        report = run_dae_benchmark(selected_cases=["reducible_nonlinear_helper"], run_simulink=False)
        markdown = render_dae_benchmark_markdown(report)
        self.assertIn("DAE Benchmark", markdown)
        self.assertIn("reducible_nonlinear_helper", markdown)

    def test_write_dae_benchmark_reports_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = write_dae_benchmark_reports(
                Path(temp_dir),
                selected_cases=["reducible_nonlinear_helper", "unsupported_nonsquare_algebraic_subsystem"],
                run_simulink=False,
            )
            self.assertEqual(report["failed_cases"], 0)
            self.assertTrue((Path(temp_dir) / "dae_benchmark.json").exists())
            self.assertTrue((Path(temp_dir) / "dae_benchmark.md").exists())


if __name__ == "__main__":
    unittest.main()


def _fake_dae_system(
    *,
    kind: str = "nonlinear_preserved_semi_explicit_dae",
    route: str = "preserved_dae",
    supported: bool = True,
    reduced_to_explicit: bool = False,
    preserved_form: object | None = object(),
):
    return SimpleNamespace(
        classification=DaeSupportClassification(
            kind=kind,
            route=route,
            supported=supported,
            python_validation_supported=supported,
            simulink_lowering_supported=supported,
        ),
        differential_states=("x",),
        algebraic_variables=("z",),
        reduced_to_explicit=reduced_to_explicit,
        preserved_form=preserved_form,
    )


def _fake_result(**overrides):
    base = {
        "dae_system": _fake_dae_system(),
        "consistent_initialization": SimpleNamespace(
            differential_initial_conditions={"x": 0.0},
            algebraic_initial_conditions={"z": 0.1},
        ),
        "graph": {"nodes": [{"id": "n1"}]},
        "first_order": None,
        "descriptor_system": {"form": "linear_descriptor"},
        "runtime": {"t_span": (0.0, 1.0), "t_eval": [0.0, 1.0]},
        "ode_result": {"t": [0.0, 1.0]},
        "state_space_result": None,
        "dae_validation": {"simulation_success": True, "residual_norm_max": 1e-9, "residual_norm_final": 1e-9},
        "dae_classification": {"route": "preserved_dae"},
    }
    base.update(overrides)
    return base


def _fake_analysis(*, dae_system=None, descriptor_system=None):
    return SimpleNamespace(
        dae_system=dae_system or _fake_dae_system(),
        descriptor_system=descriptor_system,
    )


def test_time_grid_and_runtime_override_helpers() -> None:
    case = DAE_BENCHMARK_CASES[0]
    grid = _time_grid(case)
    override = _runtime_override(case)

    assert len(grid) == case.sample_count
    assert tuple(override["t_span"]) == case.t_span
    assert override["sample_count"] == case.sample_count


def test_lower_supported_case_validates_descriptor_and_uses_first_order_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    case = DaeBenchmarkCase(
        name="descriptor_case",
        category="cat",
        latex="x=1",
        simulink_lowering_kind="descriptor",
        expected_descriptor_artifact=True,
    )
    with pytest.raises(Exception, match="descriptor artifact"):
        _lower_supported_case(case, _fake_result(descriptor_system=None))

    captured = {}
    def fake_graph_to_model(*args, **kwargs):
        captured["kwargs"] = kwargs
        return {"name": "graph_model", "blocks": {}}

    monkeypatch.setattr("simulate.dae_benchmark_suite.graph_to_simulink_model", fake_graph_to_model)
    result = _fake_result(
        dae_system=_fake_dae_system(reduced_to_explicit=False),
        first_order={"states": ["x"]},
        graph={"nodes": []},
    )
    result["dae_system"].differential_states = ()  # type: ignore[attr-defined]
    result["dae_system"].algebraic_variables = ()  # type: ignore[attr-defined]
    lowered = _lower_supported_case(DAE_BENCHMARK_CASES[2], result)

    assert lowered["name"] == "graph_model"
    assert captured["kwargs"]["state_names"] == ["x"]


def test_execute_supported_case_routes_to_descriptor_graph_and_preserved_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor_case = DaeBenchmarkCase(name="descriptor", category="cat", latex="x=1", simulink_lowering_kind="descriptor")
    monkeypatch.setattr("simulate.dae_benchmark_suite.execute_simulink_descriptor", lambda *args, **kwargs: "descriptor-result")
    assert _execute_supported_case(descriptor_case, _fake_result(), eng=object(), tolerance=1e-6) == "descriptor-result"

    monkeypatch.setattr("simulate.dae_benchmark_suite.execute_simulink_graph", lambda *args, **kwargs: "graph-result")
    assert (
        _execute_supported_case(
            DaeBenchmarkCase(name="graph", category="cat", latex="x=1"),
            _fake_result(first_order={"states": ["x"]}),
            eng=object(),
            tolerance=1e-6,
        )
        == "graph-result"
    )

    monkeypatch.setattr("simulate.dae_benchmark_suite.execute_simulink_preserved_dae_graph", lambda *args, **kwargs: "preserved-result")
    assert _execute_supported_case(DAE_BENCHMARK_CASES[2], _fake_result(), eng=object(), tolerance=1e-6) == "preserved-result"


def test_run_dae_benchmark_records_parse_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")))
    report = run_dae_benchmark(selected_cases=["reducible_nonlinear_helper"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "parse"
    assert case["stages"]["parse"]["status"] == "failed"


def test_run_dae_benchmark_records_state_extraction_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("analysis boom")),
    )

    report = run_dae_benchmark(selected_cases=["reducible_nonlinear_helper"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "state_extraction"
    assert case["stages"]["state_extraction"]["status"] == "failed"


def test_run_dae_benchmark_records_classification_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: SimpleNamespace(
            dae_system=_fake_dae_system(kind="explicit_ode", route="explicit_ode", reduced_to_explicit=True, preserved_form=None),
            descriptor_system=None,
        ),
    )

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "classification"
    assert case["stages"]["classification"]["status"] == "failed"


def test_run_dae_benchmark_records_missing_descriptor_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(
            dae_system=_fake_dae_system(
                kind="reducible_semi_explicit_dae",
                route="explicit_ode",
                reduced_to_explicit=True,
                preserved_form=None,
            ),
            descriptor_system=None,
        ),
    )

    report = run_dae_benchmark(selected_cases=["linear_descriptor_capable_balance"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "descriptor_artifact"
    assert case["stages"]["descriptor_artifact"]["status"] == "failed"


def test_run_dae_benchmark_records_missing_preserved_form(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(
            dae_system=_fake_dae_system(preserved_form=None),
            descriptor_system=None,
        ),
    )

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "preserved_form"
    assert case["stages"]["preserved_form"]["status"] == "failed"


def test_run_dae_benchmark_marks_expected_pipeline_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: SimpleNamespace(
            dae_system=_fake_dae_system(kind="unsupported_dae", route="unsupported", supported=False, preserved_form=None),
            descriptor_system=None,
        ),
    )
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.run_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("first-order differential states are required")),
    )

    report = run_dae_benchmark(selected_cases=["unsupported_high_order_preserved_dae"], run_simulink=False)

    assert report["passed_cases"] == 1
    case = report["cases"][0]
    assert case["stages"]["pipeline"]["status"] == "expected_failure"


def test_run_dae_benchmark_records_unexpected_pipeline_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(),
    )
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.run_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("pipeline boom")),
    )

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "pipeline"
    assert case["stages"]["pipeline"]["status"] == "failed"


def test_run_dae_benchmark_records_missing_python_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: SimpleNamespace(
            dae_system=_fake_dae_system(),
            descriptor_system=None,
        ),
    )
    monkeypatch.setattr("simulate.dae_benchmark_suite.run_pipeline", lambda *args, **kwargs: _fake_result(dae_validation=None))

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "python_validation"


def test_run_dae_benchmark_records_failed_python_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(),
    )
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.run_pipeline",
        lambda *args, **kwargs: _fake_result(
            dae_validation={
                "simulation_success": False,
                "message": "residual blew up",
                "residual_norm_max": 1.0,
                "residual_norm_final": 1.0,
            }
        ),
    )

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "python_validation"
    assert case["failure_reason"] == "residual blew up"


def test_run_dae_benchmark_records_lowering_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(),
    )
    monkeypatch.setattr("simulate.dae_benchmark_suite.run_pipeline", lambda *args, **kwargs: _fake_result())
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite._lower_supported_case",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("lower boom")),
    )

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=False)

    assert report["failed_cases"] == 1
    case = report["cases"][0]
    assert case["failure_stage"] == "simulink_lowering"
    assert case["stages"]["simulink_lowering"]["status"] == "failed"


def test_run_dae_benchmark_records_engine_unavailable_and_compare_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.start_engine", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("engine unavailable")))
    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=True)
    case = report["cases"][0]
    assert case["stages"]["simulink_build"]["status"] == "failed"
    assert "engine unavailable" in case["failure_reason"]

    monkeypatch.setattr("simulate.dae_benchmark_suite.start_engine", lambda *args, **kwargs: SimpleNamespace(quit=lambda: None))
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: SimpleNamespace(
            dae_system=_fake_dae_system(),
            descriptor_system=None,
        ),
    )
    monkeypatch.setattr("simulate.dae_benchmark_suite.run_pipeline", lambda *args, **kwargs: _fake_result())
    monkeypatch.setattr("simulate.dae_benchmark_suite._lower_supported_case", lambda *args, **kwargs: {"name": "model", "blocks": {}, "nodes": []})
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite._execute_supported_case",
        lambda *args, **kwargs: SimpleNamespace(model_file="/tmp/model.slx", validation={"passes": False}),
    )

    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=True)
    case = report["cases"][0]
    assert case["stages"]["simulink_compare"]["status"] == "failed"
    assert case["overall_pass"] is False


def test_run_dae_benchmark_marks_simulink_compare_success_and_missing_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.start_engine", lambda *args, **kwargs: SimpleNamespace(quit=lambda: None))
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(),
    )
    monkeypatch.setattr("simulate.dae_benchmark_suite.run_pipeline", lambda *args, **kwargs: _fake_result())
    monkeypatch.setattr("simulate.dae_benchmark_suite._lower_supported_case", lambda *args, **kwargs: {"name": "model", "blocks": {}})

    monkeypatch.setattr(
        "simulate.dae_benchmark_suite._execute_supported_case",
        lambda *args, **kwargs: SimpleNamespace(model_file="/tmp/model.slx", validation=None),
    )
    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=True)
    case = report["cases"][0]
    assert case["stages"]["simulink_compare"]["status"] == "skipped"
    assert case["overall_pass"] is True

    monkeypatch.setattr(
        "simulate.dae_benchmark_suite._execute_supported_case",
        lambda *args, **kwargs: SimpleNamespace(model_file="/tmp/model.slx", validation={"passes": True}),
    )
    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=True)
    case = report["cases"][0]
    assert case["stages"]["simulink_compare"]["status"] == "passed"
    assert case["overall_pass"] is True


def test_run_dae_benchmark_records_simulink_execution_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.dae_benchmark_suite.start_engine", lambda *args, **kwargs: SimpleNamespace(quit=lambda: None))
    monkeypatch.setattr("simulate.dae_benchmark_suite.translate_latex", lambda text: [text])
    monkeypatch.setattr(
        "simulate.dae_benchmark_suite.analyze_state_extraction",
        lambda *args, **kwargs: _fake_analysis(),
    )
    monkeypatch.setattr("simulate.dae_benchmark_suite.run_pipeline", lambda *args, **kwargs: _fake_result())
    monkeypatch.setattr("simulate.dae_benchmark_suite._lower_supported_case", lambda *args, **kwargs: {"name": "model", "blocks": {}})

    monkeypatch.setattr(
        "simulate.dae_benchmark_suite._execute_supported_case",
        lambda *args, **kwargs: (_ for _ in ()).throw(SimulinkExecutionStageError("simulink_compare", "compare boom")),
    )
    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=True)
    case = report["cases"][0]
    assert case["failure_stage"] == "simulink_compare"
    assert case["stages"]["simulink_build"]["status"] == "failed"

    monkeypatch.setattr(
        "simulate.dae_benchmark_suite._execute_supported_case",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("generic boom")),
    )
    report = run_dae_benchmark(selected_cases=["nonlinear_preserved_cubic_constraint"], run_simulink=True)
    case = report["cases"][0]
    assert case["failure_stage"] == "simulink_build"
    assert case["stages"]["simulink_build"]["status"] == "failed"


def test_render_dae_benchmark_markdown_handles_missing_classification() -> None:
    markdown = render_dae_benchmark_markdown(
        {
            "generated_cases": 1,
            "passed_cases": 0,
            "failed_cases": 1,
            "tolerance": 1e-6,
            "cases": [
                {
                    "name": "broken",
                    "category": "Category X",
                    "latex": "x=1",
                    "classification": None,
                    "metrics": {
                        "differential_state_count": None,
                        "algebraic_variable_count": None,
                        "reduced_to_explicit": None,
                        "descriptor_artifact_available": None,
                        "preserved_form_available": None,
                        "graph_nodes": None,
                        "lowered_simulink_blocks": None,
                        "residual_norm_max": None,
                        "residual_norm_final": None,
                    },
                    "stages": {"parse": {"status": "failed", "detail": "boom"}},
                    "failure_stage": "parse",
                    "failure_reason": "boom",
                    "overall_pass": False,
                }
            ],
        }
    )

    assert "failure_stage: parse" in markdown
    assert "classification:" not in markdown
