from __future__ import annotations

import unittest

import numpy as np

from canonicalize_v2.first_order import build_first_order_system
from canonicalize_v2.state_space import build_state_space_system
from latex_frontend_v2.translator import translate_latex
from simulate_v2.compare import compare_simulations
from simulate_v2.ode_sim import constant_inputs, simulate_ode_system
from simulate_v2.state_space_sim import simulate_state_space_system


class SimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
        self.first_order = build_first_order_system(equations)
        self.state_space = build_state_space_system(self.first_order)
        self.parameters = {"m": 1.0, "c": 0.4, "k": 2.0}
        self.initial_conditions = {"x": 0.0, "x_dot": 0.0}
        self.input_function = constant_inputs({"u": 1.0})
        self.t_eval = np.linspace(0.0, 10.0, 300)

    def test_direct_ode_simulation_runs(self) -> None:
        result = simulate_ode_system(
            self.first_order,
            parameter_values=self.parameters,
            initial_conditions=self.initial_conditions,
            input_function=self.input_function,
            t_eval=self.t_eval,
        )
        self.assertEqual(result["states"].shape, (300, 2))
        self.assertFalse(np.isnan(result["states"]).any())

    def test_state_space_simulation_runs(self) -> None:
        result = simulate_state_space_system(
            self.state_space,
            parameter_values=self.parameters,
            initial_conditions=self.initial_conditions,
            input_function=self.input_function,
            t_eval=self.t_eval,
        )
        self.assertEqual(result["states"].shape, (300, 2))
        self.assertFalse(np.isnan(result["states"]).any())

    def test_direct_and_state_space_match_within_tolerance(self) -> None:
        direct = simulate_ode_system(
            self.first_order,
            parameter_values=self.parameters,
            initial_conditions=self.initial_conditions,
            input_function=self.input_function,
            t_eval=self.t_eval,
        )
        state_space = simulate_state_space_system(
            self.state_space,
            parameter_values=self.parameters,
            initial_conditions=self.initial_conditions,
            input_function=self.input_function,
            t_eval=self.t_eval,
        )
        comparison = compare_simulations(direct, state_space, tolerance=1e-6)
        self.assertTrue(comparison["passes"])


if __name__ == "__main__":
    unittest.main()
