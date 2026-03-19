from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simulate_v2.benchmark_suite import (
    render_full_system_benchmark_markdown,
    run_full_system_benchmark,
    write_full_system_benchmark_reports,
)


class FullBenchmarkSuiteTests(unittest.TestCase):
    def test_benchmark_reports_supported_and_expected_failure_cases(self) -> None:
        report = run_full_system_benchmark(
            selected_cases=["basic_decay", "nonlinear_pendulum", "fail_unsupported_syntax"],
            run_simulink=False,
        )
        by_name = {entry["name"]: entry for entry in report["cases"]}
        self.assertTrue(by_name["basic_decay"]["overall_pass"])
        self.assertTrue(by_name["nonlinear_pendulum"]["overall_pass"])
        self.assertEqual(by_name["nonlinear_pendulum"]["stages"]["state_space"]["status"], "skipped")
        self.assertTrue(by_name["fail_unsupported_syntax"]["overall_pass"])
        self.assertEqual(by_name["fail_unsupported_syntax"]["failure_stage"], "parse")

    def test_markdown_report_contains_case_names(self) -> None:
        report = run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=False)
        markdown = render_full_system_benchmark_markdown(report)
        self.assertIn("Full System Benchmark", markdown)
        self.assertIn("basic_decay", markdown)

    def test_write_full_benchmark_reports_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = write_full_system_benchmark_reports(
                Path(temp_dir),
                selected_cases=["basic_decay", "fail_unsupported_syntax"],
                run_simulink=False,
            )
            self.assertEqual(report["failed_cases"], 0)
            self.assertTrue((Path(temp_dir) / "full_system_benchmark.json").exists())
            self.assertTrue((Path(temp_dir) / "full_system_benchmark.md").exists())


if __name__ == "__main__":
    unittest.main()
