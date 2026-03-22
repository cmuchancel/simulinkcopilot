from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simucompilebench.baseline import (
    _quantile,
    compare_legacy_report_to_baseline,
    load_baseline_metrics,
    summarize_legacy_benchmark_report,
    write_baseline_metrics,
)


def _sample_report() -> dict[str, object]:
    return {
        "generated_systems": 2,
        "evaluated_systems": 2,
        "passed_systems": 2,
        "failed_systems": 0,
        "average_rmse": 2.0e-11,
        "average_max_abs_error": 8.0e-11,
        "failure_categories": {},
        "systems": [
            {
                "system_id": "a",
                "overall_pass": True,
                "rmse": 1.0e-11,
                "max_abs_error": 5.0e-11,
                "parse_success": True,
                "state_extraction_success": True,
                "solve_success": True,
                "first_order_success": True,
                "state_space_success": True,
                "graph_success": True,
                "simulink_build_success": True,
                "simulation_success": True,
            },
            {
                "system_id": "b",
                "overall_pass": True,
                "rmse": 3.0e-11,
                "max_abs_error": 1.1e-10,
                "parse_success": True,
                "state_extraction_success": True,
                "solve_success": True,
                "first_order_success": True,
                "state_space_success": True,
                "graph_success": True,
                "simulink_build_success": True,
                "simulation_success": True,
            },
        ],
    }


class BaselineMetricTests(unittest.TestCase):
    def test_quantile_handles_empty_singleton_and_exact_index(self) -> None:
        self.assertEqual(_quantile([], 0.5), 0.0)
        self.assertEqual(_quantile([4.0], 0.5), 4.0)
        self.assertEqual(_quantile([1.0, 2.0, 3.0], 0.5), 2.0)

    def test_summary_contains_per_system_stage_flags(self) -> None:
        summary = summarize_legacy_benchmark_report(_sample_report())
        self.assertEqual(summary["passed_systems"], 2)
        self.assertIn("a", summary["system_summaries"])
        self.assertEqual(summary["stage_success_counts"]["graph_success"], 2)

    def test_write_and_load_baseline_metrics_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "baseline_metrics.json"
            write_baseline_metrics(target, _sample_report(), source_commit="abc123")
            loaded = load_baseline_metrics(target)
            self.assertEqual(loaded["source_commit"], "abc123")
            self.assertEqual(loaded["passed_systems"], 2)

    def test_write_baseline_metrics_omits_source_commit_when_unspecified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "baseline_metrics.json"
            baseline = write_baseline_metrics(target, _sample_report())
            self.assertNotIn("source_commit", baseline)

    def test_compare_detects_regression(self) -> None:
        baseline = summarize_legacy_benchmark_report(_sample_report())
        current = json.loads(json.dumps(_sample_report()))
        current["systems"][0]["rmse"] = 1.0e-6
        comparison = compare_legacy_report_to_baseline(current, baseline)
        self.assertFalse(comparison["matches"])
        self.assertTrue(any("rmse regression" in item for item in comparison["mismatches"]))

    def test_compare_detects_count_failure_category_and_system_set_mismatches(self) -> None:
        baseline = summarize_legacy_benchmark_report(_sample_report())
        current = json.loads(json.dumps(_sample_report()))
        current["passed_systems"] = 1
        current["failed_systems"] = 1
        current["failure_categories"] = {"solve_failure": 1}
        current["systems"] = current["systems"][:-1]

        comparison = compare_legacy_report_to_baseline(current, baseline)

        self.assertFalse(comparison["matches"])
        self.assertTrue(any("passed_systems mismatch" in item for item in comparison["mismatches"]))
        self.assertTrue(any("failed_systems mismatch" in item for item in comparison["mismatches"]))
        self.assertTrue(any("failure_categories mismatch" in item for item in comparison["mismatches"]))
        self.assertTrue(any("system_id mismatch" in item for item in comparison["mismatches"]))

    def test_compare_detects_overall_pass_and_stage_flag_mismatches(self) -> None:
        baseline = summarize_legacy_benchmark_report(_sample_report())
        current = json.loads(json.dumps(_sample_report()))
        current["systems"][0]["overall_pass"] = False
        current["systems"][0]["graph_success"] = False

        comparison = compare_legacy_report_to_baseline(current, baseline)

        self.assertFalse(comparison["matches"])
        self.assertTrue(any("overall_pass mismatch" in item for item in comparison["mismatches"]))
        self.assertTrue(any("stage_flags mismatch" in item for item in comparison["mismatches"]))


if __name__ == "__main__":
    unittest.main()
