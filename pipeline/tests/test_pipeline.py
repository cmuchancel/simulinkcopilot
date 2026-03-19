from __future__ import annotations

import unittest
from pathlib import Path

from pipeline.run_pipeline import run_pipeline
from pipeline.verbose_artifacts import write_verbose_artifacts


class PipelineTests(unittest.TestCase):
    def test_mass_spring_pipeline(self) -> None:
        result = run_pipeline(Path(__file__).resolve().parents[2] / "examples" / "mass_spring_damper.tex")
        self.assertEqual(result["extraction"].states, ("x", "x_dot"))
        self.assertTrue(result["comparison"]["passes"])
        self.assertIsNotNone(result["graph"])

    def test_nonlinear_pipeline_skips_state_space_comparison(self) -> None:
        result = run_pipeline(Path(__file__).resolve().parents[2] / "examples" / "nonlinear_pendulum.tex")
        self.assertFalse(result["linearity"]["is_linear"])
        self.assertIsNone(result["state_space"])
        self.assertIsNone(result["comparison"])

    def test_nonlinear_pipeline_allows_simulink_validation(self) -> None:
        result = run_pipeline(
            Path(__file__).resolve().parents[2] / "examples" / "nonlinear_pendulum.tex",
            run_simulink=True,
        )
        self.assertFalse(result["linearity"]["is_linear"])
        self.assertIsNone(result["state_space"])
        self.assertIsNotNone(result["simulink_result"])
        self.assertIsNotNone(result["simulink_validation"])
        self.assertIsNone(result["simulink_validation"]["vs_state_space"])
        self.assertTrue(result["simulink_validation"]["passes"])

    def test_verbose_artifacts_are_written(self) -> None:
        import tempfile

        result = run_pipeline(Path(__file__).resolve().parents[2] / "examples" / "mass_spring_damper.tex")
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = write_verbose_artifacts(result, temp_dir)
            self.assertTrue((Path(temp_dir) / "input_equations.tex").exists())
            self.assertTrue((Path(temp_dir) / "intermediate_equations.txt").exists())
            self.assertTrue((Path(temp_dir) / "state_space.txt").exists())
            self.assertTrue((Path(temp_dir) / "simulation_plot.png").exists())
            self.assertIn("output_dir", manifest)


if __name__ == "__main__":
    unittest.main()
