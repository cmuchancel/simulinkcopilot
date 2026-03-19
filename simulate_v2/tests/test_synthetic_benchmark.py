from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simulate_v2.synthetic_benchmark import (
    generate_synthetic_systems,
    render_benchmark_markdown,
    run_synthetic_benchmark,
    write_synthetic_benchmark_outputs,
)


class SyntheticBenchmarkTests(unittest.TestCase):
    def test_generator_is_deterministic(self) -> None:
        first = generate_synthetic_systems(count=12, seed=1234)
        second = generate_synthetic_systems(count=12, seed=1234)
        self.assertEqual([item.to_dict() for item in first], [item.to_dict() for item in second])
        self.assertEqual(len(first), 12)
        self.assertTrue(any(item.includes_trig for item in first))
        self.assertTrue(any(item.max_order > 1 for item in first))

    def test_small_benchmark_runs_without_simulink(self) -> None:
        systems = generate_synthetic_systems(count=6, seed=4321)
        report = run_synthetic_benchmark(systems, run_simulink=False)
        self.assertEqual(report["evaluated_systems"], 6)
        self.assertEqual(report["generated_systems"], 6)
        self.assertEqual(len(report["systems"]), 6)
        self.assertIn("success_rate_by_generated_state_count", report)

    def test_report_writer_creates_dataset_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "reports"
            data_dir = Path(temp_dir) / "data"
            report = write_synthetic_benchmark_outputs(
                output_dir=output_dir,
                data_dir=data_dir,
                count=8,
                seed=2468,
                run_simulink=False,
            )
            self.assertEqual(report["evaluated_systems"], 8)
            self.assertTrue((data_dir / "generated_systems.json").exists())
            self.assertTrue((output_dir / "benchmark.json").exists())
            self.assertTrue((output_dir / "benchmark.csv").exists())
            self.assertTrue((output_dir / "benchmark.md").exists())
            markdown = render_benchmark_markdown(report)
            self.assertIn("Synthetic Benchmark", markdown)


if __name__ == "__main__":
    unittest.main()
