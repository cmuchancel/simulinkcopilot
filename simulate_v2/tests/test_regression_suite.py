from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simulate_v2.regression_suite import render_markdown_report, run_regression_suite, write_regression_reports


class RegressionSuiteTests(unittest.TestCase):
    def test_regression_suite_reports_linear_and_nonlinear_examples(self) -> None:
        report = run_regression_suite(selected_examples=["mass_spring_damper", "nonlinear_pendulum"], run_simulink=False)
        by_name = {entry["name"]: entry for entry in report["examples"]}
        self.assertTrue(by_name["mass_spring_damper"]["overall_pass"])
        self.assertEqual(by_name["nonlinear_pendulum"]["stages"]["state_space"]["status"], "skipped")

    def test_regression_suite_reports_simulink_stage_for_required_linear_example(self) -> None:
        report = run_regression_suite(selected_examples=["mass_spring_damper"], run_simulink=True)
        entry = report["examples"][0]
        self.assertEqual(entry["stages"]["simulink_build"]["status"], "passed")
        self.assertEqual(entry["stages"]["simulink_compare"]["status"], "passed")

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
