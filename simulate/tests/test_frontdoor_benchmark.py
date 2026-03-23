from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simulate.frontdoor_benchmark import (
    build_frontdoor_payloads,
    render_frontdoor_benchmark_markdown,
    run_frontdoor_benchmark,
    write_frontdoor_benchmark_outputs,
)
from simulate.synthetic_benchmark import generate_synthetic_systems


class FrontDoorBenchmarkTests(unittest.TestCase):
    def test_payload_builder_generates_all_three_front_doors(self) -> None:
        spec = generate_synthetic_systems(count=1, seed=1357)[0]
        payloads = build_frontdoor_payloads(spec)
        self.assertTrue(payloads.latex_text)
        self.assertTrue(payloads.matlab_symbolic_equations)
        self.assertTrue(payloads.matlab_equation_text_equations)
        self.assertTrue(all("==" in text for text in payloads.matlab_symbolic_equations))

    def test_small_frontdoor_benchmark_runs_without_simulink(self) -> None:
        systems = generate_synthetic_systems(count=6, seed=9753)
        report = run_frontdoor_benchmark(systems, run_simulink=False)
        self.assertEqual(report["generated_systems"], 6)
        self.assertEqual(report["evaluated_frontdoor_runs"], 18)
        self.assertEqual(set(report["success_by_source_type"]), {"latex", "matlab_symbolic", "matlab_equation_text"})

    def test_frontdoor_benchmark_writer_creates_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "reports"
            data_dir = Path(temp_dir) / "data"
            report = write_frontdoor_benchmark_outputs(
                output_dir=output_dir,
                data_dir=data_dir,
                count=6,
                seed=8642,
                run_simulink=False,
            )
            self.assertEqual(report["generated_systems"], 6)
            self.assertTrue((data_dir / "frontdoor_benchmark_systems.json").exists())
            self.assertTrue((output_dir / "frontdoor_benchmark.json").exists())
            self.assertTrue((output_dir / "frontdoor_benchmark.csv").exists())
            self.assertTrue((output_dir / "frontdoor_benchmark.md").exists())
            markdown = render_frontdoor_benchmark_markdown(report)
            self.assertIn("Front-Door Benchmark", markdown)


if __name__ == "__main__":
    unittest.main()
