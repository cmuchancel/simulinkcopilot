from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simulate.dae_benchmark_suite import (
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
