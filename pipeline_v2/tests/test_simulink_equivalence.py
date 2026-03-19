from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from pipeline.run_pipeline import run_pipeline as run_pipeline_v1
from pipeline_v2.run_pipeline import run_pipeline as run_pipeline_v2
from simulink_v2.engine import start_engine


class SimulinkEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.eng = start_engine(retries=1, retry_delay_seconds=1.0)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.eng.quit()

    def _assert_simulink_match(self, example_name: str) -> None:
        path = Path(__file__).resolve().parents[2] / "examples" / example_name
        result_v1 = run_pipeline_v1(path, run_simulink=True, matlab_engine=self.eng)
        result_v2 = run_pipeline_v2(path, run_simulink=True, matlab_engine=self.eng)

        self.assertEqual(result_v1["equation_dicts"], result_v2["equation_dicts"])
        self.assertEqual(result_v1["graph"], result_v2["graph"])
        self.assertTrue(np.allclose(result_v1["ode_result"]["states"], result_v2["ode_result"]["states"]))
        self.assertTrue(np.allclose(result_v1["simulink_result"]["t"], result_v2["simulink_result"]["t"]))
        self.assertTrue(np.allclose(result_v1["simulink_result"]["states"], result_v2["simulink_result"]["states"], atol=1e-8))
        self.assertAlmostEqual(
            float(result_v1["simulink_validation"]["vs_ode"]["rmse"]),
            float(result_v2["simulink_validation"]["vs_ode"]["rmse"]),
            places=8,
        )

    def test_linear_simulink_matches_v1(self) -> None:
        self._assert_simulink_match("mass_spring_damper.tex")

    def test_nonlinear_simulink_matches_v1(self) -> None:
        self._assert_simulink_match("nonlinear_pendulum.tex")


if __name__ == "__main__":
    unittest.main()
