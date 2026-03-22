from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from canonicalize.first_order import build_first_order_system
from canonicalize.state_space import build_state_space_system
from latex_frontend.translator import translate_latex
from simulate.compare import compare_simulations
from simulate.ode_sim import constant_inputs, simulate_ode_system
from simulate.state_space_sim import simulate_state_space_system
from states.extract_states import extract_states


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

    def test_multi_input_linear_system_matches_state_space(self) -> None:
        equations = translate_latex(r"\dot{x}=a x+b u_1+c u_2")
        extraction = extract_states(
            equations,
            mode="configured",
            symbol_config={"a": "parameter", "b": "parameter", "c": "parameter", "u_1": "input", "u_2": "input"},
        )
        first_order = build_first_order_system(equations, extraction=extraction)
        state_space = build_state_space_system(first_order)
        parameters = {"a": -0.4, "b": 2.0, "c": -1.0}
        initial_conditions = {"x": 0.25}
        input_function = lambda t: {"u_1": float(np.sin(t)), "u_2": float(np.cos(t))}
        t_eval = np.linspace(0.0, 4.0, 240)

        direct = simulate_ode_system(
            first_order,
            parameter_values=parameters,
            initial_conditions=initial_conditions,
            input_function=input_function,
            t_eval=t_eval,
        )
        state_space_result = simulate_state_space_system(
            state_space,
            parameter_values=parameters,
            initial_conditions=initial_conditions,
            input_function=input_function,
            t_eval=t_eval,
        )

        self.assertEqual(direct["input_names"], ["u_1", "u_2"])
        self.assertEqual(state_space_result["input_names"], ["u_1", "u_2"])
        comparison = compare_simulations(direct, state_space_result, tolerance=1e-6)
        self.assertTrue(comparison["passes"])

    def test_simulators_raise_runtime_error_on_solver_failure(self) -> None:
        class FailedSolution:
            success = False
            message = "solver broke"

        with patch("simulate.ode_sim.solve_ivp", return_value=FailedSolution()):
            with self.assertRaisesRegex(RuntimeError, "ODE simulation failed: solver broke"):
                simulate_ode_system(
                    self.first_order,
                    parameter_values=self.parameters,
                    initial_conditions=self.initial_conditions,
                    input_function=self.input_function,
                    t_eval=self.t_eval,
                )

        with patch("simulate.state_space_sim.solve_ivp", return_value=FailedSolution()):
            with self.assertRaisesRegex(RuntimeError, "State-space simulation failed: solver broke"):
                simulate_state_space_system(
                    self.state_space,
                    parameter_values=self.parameters,
                    initial_conditions=self.initial_conditions,
                    input_function=self.input_function,
                    t_eval=self.t_eval,
                )

    def test_state_space_simulation_without_inputs_exercises_output_path(self) -> None:
        equations = translate_latex(r"\dot{x}=-ax")
        extraction = extract_states(
            equations,
            mode="configured",
            symbol_config={"a": "parameter"},
        )
        first_order = build_first_order_system(equations, extraction=extraction)
        state_space = build_state_space_system(first_order)

        result = simulate_state_space_system(
            state_space,
            parameter_values={"a": 0.5},
            initial_conditions={"x": 1.0},
            t_eval=np.linspace(0.0, 0.2, 3),
        )

        self.assertEqual(result["input_names"], [])
        self.assertEqual(result["inputs"].shape, (3, 0))


if __name__ == "__main__":
    unittest.main()
