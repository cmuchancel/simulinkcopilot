from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from canonicalize.first_order import build_first_order_system
from canonicalize.state_space import build_state_space_system
from backend.graph_to_simulink import graph_to_simulink_model
from backend.simulate_simulink import simulation_model_params, simulate_simulink_model
from backend.validate_simulink import compare_simulink_results
from ir.graph_lowering import lower_first_order_system_graph
from latex_frontend.translator import translate_latex
from simulate.ode_sim import constant_inputs, simulate_ode_system
from simulate.state_space_sim import simulate_state_space_system
from simulink.engine import start_engine


class BackendIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.eng = start_engine(retries=1, retry_delay_seconds=1.0)
        cls.output_dir = Path(__file__).resolve().parents[2] / "generated_models" / "backend_tests"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.eng.quit()

    def test_mass_spring_builds_and_matches_python(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
        first_order = build_first_order_system(equations)
        state_space = build_state_space_system(first_order)
        graph = lower_first_order_system_graph(first_order, name="mass_spring_backend_test")
        params = {"m": 1.0, "c": 0.4, "k": 2.0}
        inputs = {"u": 1.0}
        initial_conditions = {"x": 0.0, "x_dot": 0.0}
        t_eval = np.linspace(0.0, 10.0, 300)
        model = graph_to_simulink_model(
            graph,
            name="mass_spring_backend_test",
            state_names=first_order["states"],
            parameter_values=params,
            input_values=inputs,
            model_params=simulation_model_params(t_span=(0.0, 10.0), t_eval=t_eval),
        )
        simulink_result = simulate_simulink_model(self.eng, model, output_dir=self.output_dir)
        ode_result = simulate_ode_system(
            first_order,
            parameter_values=params,
            initial_conditions=initial_conditions,
            input_function=constant_inputs(inputs),
            t_eval=t_eval,
        )
        state_space_result = simulate_state_space_system(
            state_space,
            parameter_values=params,
            initial_conditions=initial_conditions,
            input_function=constant_inputs(inputs),
            t_eval=t_eval,
        )
        validation = compare_simulink_results(
            simulink_result,
            ode_result,
            state_space_result,
            tolerance=1e-6,
        )
        self.assertTrue(validation["passes"])


if __name__ == "__main__":
    unittest.main()
