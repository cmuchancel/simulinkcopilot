from __future__ import annotations

import unittest

from simucompilebench.catalog import build_simucompilebench_specs
from simucompilebench.runner import run_extended_benchmark


class BenchmarkRunnerTests(unittest.TestCase):
    def test_extended_runner_handles_success_and_expected_failure(self) -> None:
        selected_ids = {"controlled_feedback_pair", "adversarial_ambiguous_forcing"}
        specs = [spec for spec in build_simucompilebench_specs(include_legacy=False) if spec.system_id in selected_ids]
        report = run_extended_benchmark(specs, run_simulink=False)
        by_id = {item["system_id"]: item for item in report["systems"]}
        self.assertTrue(by_id["controlled_feedback_pair"]["overall_pass"])
        self.assertEqual(by_id["controlled_feedback_pair"]["benchmark_result"], "pass")
        self.assertTrue(by_id["adversarial_ambiguous_forcing"]["overall_pass"])
        self.assertEqual(by_id["adversarial_ambiguous_forcing"]["benchmark_result"], "expected_failure_observed")


if __name__ == "__main__":
    unittest.main()
