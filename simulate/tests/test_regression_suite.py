from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pytest

from simulate.regression_suite import render_markdown_report, run_regression_suite, write_regression_reports


class RegressionSuiteTests(unittest.TestCase):
    def test_regression_suite_reports_linear_and_nonlinear_examples(self) -> None:
        report = run_regression_suite(selected_examples=["mass_spring_damper", "nonlinear_pendulum"], run_simulink=False)
        by_name = {entry["name"]: entry for entry in report["examples"]}
        self.assertTrue(by_name["mass_spring_damper"]["overall_pass"])
        self.assertEqual(by_name["nonlinear_pendulum"]["stages"]["state_space"]["status"], "skipped")

    @pytest.mark.matlab
    @pytest.mark.slow
    def test_regression_suite_reports_simulink_stage_for_required_linear_example(self) -> None:
        report = run_regression_suite(selected_examples=["mass_spring_damper"], run_simulink=True)
        entry = report["examples"][0]
        self.assertEqual(entry["stages"]["simulink_build"]["status"], "passed")
        self.assertEqual(entry["stages"]["simulink_compare"]["status"], "passed")

    @pytest.mark.matlab
    @pytest.mark.slow
    def test_regression_suite_reports_simulink_stage_for_nonlinear_example(self) -> None:
        report = run_regression_suite(selected_examples=["nonlinear_pendulum"], run_simulink=True)
        entry = report["examples"][0]
        self.assertEqual(entry["stages"]["state_space"]["status"], "skipped")
        self.assertEqual(entry["stages"]["simulink_build"]["status"], "passed")
        self.assertEqual(entry["stages"]["simulink_compare"]["status"], "passed")

    def test_markdown_report_contains_summary(self) -> None:
        report = run_regression_suite(selected_examples=["mass_spring_damper"], run_simulink=False)
        markdown = render_markdown_report(report)
        self.assertIn("Phase 3 Report", markdown)
        self.assertIn("mass_spring_damper", markdown)

    def test_write_regression_reports_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = write_regression_reports(Path(temp_dir), selected_examples=["mass_spring_damper"], run_simulink=False)
            self.assertEqual(report["failed_examples"], 0)
            self.assertTrue((Path(temp_dir) / "phase2_report.json").exists())
            self.assertTrue((Path(temp_dir) / "phase2_report.md").exists())
            self.assertTrue((Path(temp_dir) / "phase3_report.json").exists())
            self.assertTrue((Path(temp_dir) / "phase3_report.md").exists())


if __name__ == "__main__":
    unittest.main()


def _fake_pipeline_results(
    *,
    comparison=None,
    state_space=None,
    simulink_validation=None,
    simulink_result=None,
):
    return {
        "comparison": comparison,
        "state_space": state_space,
        "simulink_validation": simulink_validation,
        "simulink_result": simulink_result,
    }


def _fake_summary(*, is_linear=True):
    return {
        "linearity": {"is_linear": is_linear},
        "graph": {"ops": ["add"]},
        "comparison": {"kind": "dummy"},
        "simulink": {"kind": "dummy"},
    }


def test_run_regression_suite_records_engine_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.regression_suite.start_engine", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("engine unavailable")))
    monkeypatch.setattr("simulate.regression_suite.example_paths", lambda: [Path("/tmp/mass_spring_damper.tex")])

    report = run_regression_suite(selected_examples=["mass_spring_damper"], run_simulink=True)

    assert report["failed_examples"] == 1
    example = report["examples"][0]
    assert example["error"] == "engine unavailable"
    assert example["stages"]["simulink_build"]["status"] == "failed"


def test_run_regression_suite_records_comparison_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulate.regression_suite.example_paths", lambda: [Path("/tmp/mass_spring_damper.tex")])
    monkeypatch.setattr(
        "simulate.regression_suite.run_pipeline",
        lambda *args, **kwargs: _fake_pipeline_results(
            comparison={"passes": False, "rmse": 1.0, "max_abs_error": 2.0},
            state_space={"A": [[1.0]]},
        ),
    )
    monkeypatch.setattr("simulate.regression_suite.summarize_pipeline_results", lambda results: _fake_summary())

    report = run_regression_suite(selected_examples=["mass_spring_damper"], run_simulink=False)

    assert report["failed_examples"] == 1
    example = report["examples"][0]
    assert example["stages"]["comparison"]["status"] == "failed"


def test_run_regression_suite_records_simulink_compare_failure_and_quits_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = SimpleNamespace(quit=lambda: setattr(engine, "quit_called", True), quit_called=False)
    monkeypatch.setattr("simulate.regression_suite.start_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr("simulate.regression_suite.example_paths", lambda: [Path("/tmp/mass_spring_damper.tex")])
    monkeypatch.setattr(
        "simulate.regression_suite.run_pipeline",
        lambda *args, **kwargs: _fake_pipeline_results(
            comparison={"passes": True, "rmse": 0.0, "max_abs_error": 0.0},
            state_space={"A": [[1.0]]},
            simulink_result={"model_file": "/tmp/model.slx"},
            simulink_validation={"passes": False, "vs_ode": {"rmse": 1.0, "max_abs_error": 2.0}},
        ),
    )
    monkeypatch.setattr("simulate.regression_suite.summarize_pipeline_results", lambda results: _fake_summary())

    report = run_regression_suite(selected_examples=["mass_spring_damper"], run_simulink=True)

    assert engine.quit_called is True
    assert report["failed_examples"] == 1
    example = report["examples"][0]
    assert example["stages"]["simulink_compare"]["status"] == "failed"


def test_render_markdown_report_includes_error_examples() -> None:
    markdown = render_markdown_report(
        {
            "generated_examples": 1,
            "passed_examples": 0,
            "failed_examples": 1,
            "supported_syntax": [],
            "supported_system_classes": [],
            "known_unsupported_classes": [],
            "graph_lowering_coverage": [],
            "simulink_examples": [],
            "tolerance": 1e-6,
            "examples": [
                {
                    "name": "broken",
                    "path": "/tmp/broken.tex",
                    "expected_linear": True,
                    "error": "parse boom",
                    "stages": {"parse": {"status": "failed", "detail": "parse boom"}},
                    "overall_pass": False,
                }
            ],
        }
    )

    assert "- error: parse boom" in markdown
