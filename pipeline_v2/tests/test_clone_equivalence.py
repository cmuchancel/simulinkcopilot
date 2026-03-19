from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from pipeline.run_pipeline import run_pipeline as run_pipeline_v1
from pipeline_v2.run_pipeline import run_pipeline as run_pipeline_v2


class CloneEquivalenceTests(unittest.TestCase):
    def _assert_pipeline_match(self, example_name: str) -> None:
        path = Path(__file__).resolve().parents[2] / "examples" / example_name
        result_v1 = run_pipeline_v1(path, run_simulink=False)
        result_v2 = run_pipeline_v2(path, run_simulink=False)

        self.assertEqual(result_v1["equation_dicts"], result_v2["equation_dicts"])
        self.assertEqual(result_v1["first_order"], result_v2["first_order"])
        self.assertEqual(result_v1["graph"], result_v2["graph"])
        self.assertEqual(result_v1["linearity"], result_v2["linearity"])
        self.assertTrue(np.allclose(result_v1["ode_result"]["states"], result_v2["ode_result"]["states"]))
        self.assertTrue(np.allclose(result_v1["ode_result"]["t"], result_v2["ode_result"]["t"]))

    def test_linear_clone_matches_v1(self) -> None:
        self._assert_pipeline_match("mass_spring_damper.tex")

    def test_nonlinear_clone_matches_v1(self) -> None:
        self._assert_pipeline_match("nonlinear_pendulum.tex")


if __name__ == "__main__":
    unittest.main()
