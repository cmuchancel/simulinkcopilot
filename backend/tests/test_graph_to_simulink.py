from __future__ import annotations

from collections import Counter
import unittest

from canonicalize.first_order import build_first_order_system
from backend.graph_to_simulink import graph_to_simulink_model
from ir.graph_lowering import lower_first_order_system_graph
from latex_frontend.translator import translate_latex
from states.extract_states import extract_states


class GraphToSimulinkTests(unittest.TestCase):
    def test_mass_spring_graph_maps_to_simulink_blocks(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u"))
        graph = lower_first_order_system_graph(first_order, name="mass_spring")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"m": 1.0, "c": 0.4, "k": 2.0},
            input_values={"u": 1.0},
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("Integrator", block_types)
        self.assertIn("Outport", block_types)
        self.assertEqual([entry["name"] for entry in model["outputs"]], ["x", "x_dot"])

    def test_pow_parameter_subtree_is_constant_folded(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-w_0^2x+u"))
        graph = lower_first_order_system_graph(first_order, name="oscillator")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"w_0": 1.5},
            input_values={"u": 1.0},
        )
        parameter_literals = {
            str(value)
            for spec in model["blocks"].values()
            for value in spec["params"].values()
        }
        self.assertIn("2.25", parameter_literals)

    def test_time_varying_input_maps_to_from_workspace_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"m": 1.0, "c": 0.2, "k": 2.0},
            input_signals={"u": {"time": [0.0, 1.0], "values": [0.0, 1.0]}},
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("FromWorkspace", block_types)
        self.assertTrue(model["workspace_variables"])

    def test_multi_input_sources_map_cleanly_to_backend_blocks(self) -> None:
        equations = translate_latex(r"\dot{x}=a x+b u_1+c u_2")
        extraction = extract_states(
            equations,
            mode="configured",
            symbol_config={"a": "parameter", "b": "parameter", "c": "parameter", "u_1": "input", "u_2": "input"},
        )
        first_order = build_first_order_system(equations, extraction=extraction)
        graph = lower_first_order_system_graph(first_order, name="mimo_driven")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"a": -0.4, "b": 2.0, "c": -1.0},
            input_values={"u_1": 1.5},
            input_signals={"u_2": {"time": [0.0, 1.0], "values": [0.0, 1.0]}},
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("Constant", block_types)
        self.assertIn("FromWorkspace", block_types)
        self.assertIn("u_2", "".join(model["workspace_variables"].keys()))

    def test_declared_independent_variable_maps_to_clock_block(self) -> None:
        equations = translate_latex(r"\dot{x}=-t x+u")
        extraction = extract_states(
            equations,
            mode="configured",
            symbol_config={"t": "independent_variable", "u": "input"},
        )
        first_order = build_first_order_system(equations, extraction=extraction)
        graph = lower_first_order_system_graph(first_order, name="time_varying")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_values={"u": 1.0},
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("Clock", block_types)

    def test_sine_graph_maps_to_trigonometric_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\ddot{\theta}+\frac{g}{l}\sin(\theta)=0"))
        graph = lower_first_order_system_graph(first_order, name="pendulum")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"g": 9.81, "l": 1.0},
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("TrigonometricFunction", block_types)

    def test_exp_log_and_sec_graph_map_to_backend_blocks(self) -> None:
        equations = translate_latex(r"\dot{x}=\exp(-ax)+u+\ln(b)+\sec(x)")
        extraction = extract_states(equations, mode="configured", symbol_config={"b": "parameter", "u": "input"})
        first_order = build_first_order_system(equations, extraction=extraction)
        graph = lower_first_order_system_graph(first_order, name="function_blocks")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"a": 0.5, "b": 2.0},
            input_values={"u": 1.0},
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("MathFunction", block_types)
        self.assertIn("TrigonometricFunction", block_types)
        self.assertIn("Divide", block_types)

    def test_abs_and_sqrt_graph_map_to_backend_blocks(self) -> None:
        equations = translate_latex(r"\dot{x}=\sqrt{x}+\lvert x \rvert")
        first_order = build_first_order_system(equations)
        graph = lower_first_order_system_graph(first_order, name="abs_sqrt_blocks")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("MathFunction", block_types)
        self.assertIn("Abs", block_types)

    def test_non_integer_power_uses_math_function_chain(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=x^{\frac{1}{2}}"))
        graph = lower_first_order_system_graph(first_order, name="fractional_power")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
        )
        math_function_blocks = [
            spec for spec in model["blocks"].values() if spec["type"] == "MathFunction"
        ]
        operators = {spec["params"].get("Operator") for spec in math_function_blocks}
        self.assertTrue({"log", "exp"}.issubset(operators))

    def test_integer_self_power_does_not_duplicate_destination_ports(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-ax+x^2"))
        graph = lower_first_order_system_graph(first_order, name="self_power")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"a": 0.2},
        )
        destination_counts = Counter(
            (connection["system"], connection["dst_block"], connection["dst_port"])
            for connection in model["connections"]
        )
        duplicates = {key: count for key, count in destination_counts.items() if count > 1}
        self.assertFalse(duplicates)


if __name__ == "__main__":
    unittest.main()
