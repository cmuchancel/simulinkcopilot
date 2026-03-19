from __future__ import annotations

from collections import Counter
import unittest

from canonicalize_v2.first_order import build_first_order_system
from backend_v2.graph_to_simulink import graph_to_simulink_model
from ir_v2.graph_lowering import lower_first_order_system_graph
from latex_frontend_v2.translator import translate_latex
from states_v2.extract_states import extract_states


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
        self.assertIn("Subsystem", block_types)
        self.assertIn("Outport", block_types)
        self.assertEqual([entry["name"] for entry in model["outputs"]], ["x", "x_dot"])
        self.assertEqual(
            [block_id for block_id, spec in model["blocks"].items() if spec["type"] == "Subsystem"],
            ["subsystem_x"],
        )

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
        labels = {connection["label"] for connection in model["connections"] if connection.get("label")}
        self.assertIn("q", labels)
        self.assertTrue(any("sin" in label for label in labels))

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

    def test_coupled_trig_difference_reuses_shared_expression_at_root(self) -> None:
        first_order = build_first_order_system(
            translate_latex(
                r"\dot{\theta_1}=\omega_1"
                "\n"
                r"\dot{\omega_1}=-\sin(\theta_1-\theta_2)"
                "\n"
                r"\dot{\theta_2}=\omega_2"
                "\n"
                r"\dot{\omega_2}=\sin(\theta_1-\theta_2)"
            )
        )
        graph = lower_first_order_system_graph(first_order, name="coupled_trig_difference")
        model = graph_to_simulink_model(graph, state_names=first_order["states"])
        trig_blocks = [
            spec
            for spec in model["blocks"].values()
            if spec["type"] == "TrigonometricFunction"
        ]
        self.assertEqual(len(trig_blocks), 1)
        self.assertEqual(trig_blocks[0]["system"], "root")

    def test_group_subsystems_and_traceability_are_present(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m_1\ddot{x}_1+c_1\dot{x}_1+k_1 x_1=u"))
        graph = lower_first_order_system_graph(first_order, name="single_group")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"m_1": 1.0, "c_1": 0.2, "k_1": 2.0},
            input_values={"u": 1.0},
        )
        self.assertIn("subsystem_x_1", model["blocks"])
        self.assertEqual(model["blocks"]["subsystem_x_1"]["type"], "Subsystem")
        internal_integrators = [
            spec
            for spec in model["blocks"].values()
            if spec["system"] == "subsystem_x_1" and spec["type"] == "Integrator"
        ]
        self.assertEqual(len(internal_integrators), 2)
        labels = [connection["label"] for connection in model["connections"] if connection.get("label")]
        self.assertTrue(any("x_1" in label for label in labels))


if __name__ == "__main__":
    unittest.main()
