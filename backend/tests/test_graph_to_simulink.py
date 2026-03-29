from __future__ import annotations

from collections import Counter
import unittest

from canonicalize.first_order import build_first_order_system
from backend.graph_to_simulink import graph_to_simulink_model
from ir.graph_lowering import lower_first_order_system_graph, lower_semi_explicit_dae_graph
from latex_frontend.translator import translate_latex
from states.extract_states import analyze_state_extraction, extract_states


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

    def test_pow_parameter_subtree_preserves_named_symbol_source(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-w_0^2x+u"))
        graph = lower_first_order_system_graph(first_order, name="oscillator")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"w_0": 1.5},
            input_values={"u": 1.0},
        )
        root_names = {spec["name"] for spec in model["blocks"].values() if spec["system"] == "root"}
        self.assertIn("w_0", root_names)
        product_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "Product"]
        self.assertTrue(product_blocks)

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
        self.assertEqual(model["workspace_variables"], {})
        from_workspace_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "FromWorkspace"]
        self.assertTrue(from_workspace_blocks[0]["params"]["VariableName"].startswith("["))

    def test_native_step_input_spec_maps_to_step_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_step")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"m": 1.0, "c": 0.2, "k": 2.0},
            input_specs={"u": {"kind": "step", "amplitude": 2.0, "start_time": 1.5, "bias": -0.5}},
            input_signals={"u": {"time": [0.0, 1.0], "values": [0.0, 1.0]}},
        )
        step_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "Step"]
        self.assertTrue(step_blocks)
        self.assertEqual(step_blocks[0]["name"], "u")
        self.assertEqual(step_blocks[0]["params"], {"Time": "1.5", "Before": "-0.5", "After": "1.5"})
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertNotIn("FromWorkspace", block_types)

    def test_native_ramp_input_spec_maps_to_ramp_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_ramp")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={"u": {"kind": "ramp", "slope": 2.0, "start_time": 1.5, "initial_output": -1.0}},
        )
        ramp_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "Ramp"]
        self.assertTrue(ramp_blocks)
        self.assertEqual(ramp_blocks[0]["params"], {"slope": "2", "start": "1.5", "InitialOutput": "-1"})
        self.assertNotIn("FromWorkspace", {spec["type"] for spec in model["blocks"].values()})

    def test_native_impulse_input_spec_maps_to_pulse_generator_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_impulse")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={"u": {"kind": "impulse", "amplitude": 3.0, "start_time": 1.0, "width": 0.2, "period": 5.0}},
        )
        pulse_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "PulseGenerator"]
        self.assertTrue(pulse_blocks)
        self.assertEqual(
            pulse_blocks[0]["params"],
            {"PulseType": "Time based", "Amplitude": "15", "Period": "5", "PulseWidth": "4", "PhaseDelay": "1"},
        )
        self.assertNotIn("FromWorkspace", {spec["type"] for spec in model["blocks"].values()})

    def test_native_sum_of_steps_input_spec_uses_multiple_step_blocks(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_sum")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={
                "u": {
                    "kind": "sum",
                    "terms": [
                        {"kind": "constant", "value": -1.0},
                        {"kind": "step", "amplitude": 2.0, "start_time": 1.0, "bias": 0.0},
                        {"kind": "step", "amplitude": 3.0, "start_time": 2.0, "bias": 0.0},
                    ],
                }
            },
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertEqual(block_types.count("Step"), 2)
        self.assertIn("Constant", block_types)
        self.assertIn("Sum", block_types)
        self.assertNotIn("FromWorkspace", block_types)

    def test_native_saturation_input_spec_builds_sine_source_chain(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_sat")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={
                "u": {
                    "kind": "saturation",
                    "input": {"kind": "sine", "amplitude": 2.0, "frequency": 0.5, "phase": 0.25, "bias": 0.0},
                    "lower_limit": -0.5,
                    "upper_limit": 0.75,
                }
            },
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("SineWave", block_types)
        self.assertIn("Saturation", block_types)
        self.assertNotIn("FromWorkspace", block_types)

    def test_native_square_input_spec_builds_sign_and_sine_chain(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_square")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={"u": {"kind": "square", "amplitude": 2.0, "frequency": 3.0, "phase": -0.1, "bias": 1.0}},
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("SineWave", block_types)
        self.assertIn("Sign", block_types)
        self.assertIn("Gain", block_types)
        self.assertIn("Sum", block_types)

    def test_native_repeating_sequence_input_spec_uses_repeating_sequence_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_sawtooth")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={"u": {"kind": "sawtooth", "amplitude": 1.5, "frequency": 4.0, "phase": 0.3, "bias": -0.25}},
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("RepeatingSequence", block_types)
        self.assertIn("TransportDelay", block_types)

    def test_native_piecewise_input_spec_builds_switch_chain(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_piecewise")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={
                "u": {
                    "kind": "piecewise",
                    "branches": [
                        {
                            "condition": {"kind": "compare", "lhs": {"kind": "time"}, "rhs": {"kind": "constant", "value": 1.0}, "op": "<"},
                            "value": {"kind": "constant", "value": 0.0},
                        },
                        {
                            "condition": {"kind": "compare", "lhs": {"kind": "time"}, "rhs": {"kind": "constant", "value": 2.0}, "op": "<"},
                            "value": {"kind": "constant", "value": 2.0},
                        },
                    ],
                    "otherwise": {"kind": "constant", "value": 3.0},
                }
            },
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("Switch", block_types)
        self.assertIn("RelationalOperator", block_types)
        self.assertIn("Clock", block_types)

    def test_native_dead_zone_random_and_composite_input_specs_build_expected_blocks(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)+v(t)+w(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_native_ops")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={
                "u": {"kind": "dead_zone", "input": {"kind": "sine", "amplitude": 1.0, "frequency": 2.0, "phase": 0.0, "bias": 0.0}, "lower_limit": -0.5, "upper_limit": 0.5},
                "v": {"kind": "random_number", "minimum": -1.0, "maximum": 1.0, "seed": 7, "sample_time": 0.1},
                "w": {
                    "kind": "product",
                    "terms": [
                        {"kind": "exp", "input": {"kind": "product", "terms": [{"kind": "constant", "value": -2.0}, {"kind": "time"}]}},
                        {"kind": "sine", "amplitude": 1.0, "frequency": 1.0, "phase": 0.0, "bias": 0.0},
                    ],
                },
            },
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("DeadZone", block_types)
        self.assertIn("UniformRandomNumber", block_types)
        self.assertIn("MathFunction", block_types)
        self.assertIn("Product", block_types)

    def test_expression_input_spec_maps_supported_functions_to_native_blocks(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_expression_fallback")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={"u": {"kind": "expression", "expression": "atan(t)", "time_variable": "t"}},
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("TrigonometricFunction", block_types)
        self.assertIn("Clock", block_types)
        self.assertNotIn("FromWorkspace", block_types)
        self.assertNotIn("MATLABFunction", block_types)

    def test_unsupported_expression_input_spec_falls_back_to_matlab_function_block(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-x+u(t)"))
        graph = lower_first_order_system_graph(first_order, name="driven_expression_unsupported")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            input_specs={"u": {"kind": "expression", "expression": "erf(t)", "time_variable": "t"}},
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("MATLABFunction", block_types)
        self.assertIn("Clock", block_types)
        self.assertNotIn("FromWorkspace", block_types)
        function_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "MATLABFunction"]
        self.assertIn("erf(t)", function_blocks[0]["metadata"]["matlab_function_script"])

    def test_named_parameter_denominator_is_preserved_as_visible_symbol_source(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u"))
        graph = lower_first_order_system_graph(first_order, name="mass_spring")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"m": 5.0, "c": 10.0, "k": 20.0},
            input_values={"u": 1.0},
        )
        root_names = {spec["name"] for spec in model["blocks"].values() if spec["system"] == "root"}
        self.assertIn("m", root_names)
        divide_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "Divide"]
        self.assertTrue(divide_blocks)

    def test_literal_negative_factor_uses_negation_gain_instead_of_constant_minus_one_source(self) -> None:
        equations = translate_latex(r"\dot{x}=-cu")
        extraction = extract_states(
            equations,
            mode="configured",
            symbol_config={"c": "parameter", "u": "input"},
        )
        first_order = build_first_order_system(equations, extraction=extraction)
        graph = lower_first_order_system_graph(first_order, name="negative_gain")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"c": 2.0},
            input_values={"u": 1.0},
        )
        root_constants = {
            spec["params"].get("Value")
            for spec in model["blocks"].values()
            if spec["system"] == "root" and spec["type"] == "Constant"
        }
        self.assertNotIn("-1", root_constants)
        gains = [spec for spec in model["blocks"].values() if spec["type"] == "Gain"]
        self.assertTrue(any(spec["params"].get("Gain") == "-1" for spec in gains))

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
        self.assertEqual(model["workspace_variables"], {})
        from_workspace_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "FromWorkspace"]
        self.assertTrue(from_workspace_blocks[0]["params"]["VariableName"].startswith("["))

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
        visible_names = {spec["name"] for spec in model["blocks"].values()}
        self.assertIn("t", visible_names)
        self.assertIn("u", visible_names)

    def test_parameter_and_input_blocks_use_user_facing_symbol_names(self) -> None:
        first_order = build_first_order_system(translate_latex(r"\dot{x}=-a x+u"))
        graph = lower_first_order_system_graph(first_order, name="symbol_labels")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"a": 0.5},
            input_values={"u": 1.0},
        )
        root_names = {
            spec["name"]
            for spec in model["blocks"].values()
            if spec["system"] == "root"
        }
        self.assertIn("a", root_names)
        self.assertIn("u", root_names)
        self.assertNotIn("symbol_a", root_names)
        self.assertNotIn("input_u", root_names)

    def test_single_state_group_model_is_flattened_without_subsystem_port_plumbing(self) -> None:
        first_order = build_first_order_system(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u(t)"))
        graph = lower_first_order_system_graph(first_order, name="flat_single_group")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"m": 5.0, "c": 10.0, "k": 20.0},
            input_specs={"u": {"kind": "step", "amplitude": 1.0, "start_time": 0.0, "bias": 0.0}},
        )
        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertNotIn("Subsystem", block_types)
        non_root_ports = [
            spec
            for spec in model["blocks"].values()
            if spec["system"] != "root" and spec["type"] in {"Inport", "Outport"}
        ]
        self.assertFalse(non_root_ports)

    def test_multi_state_group_model_keeps_subsystem_structure(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}=-a x+u",
                    r"\dot{y}=-b y+v",
                ]
            )
        )
        first_order = build_first_order_system(equations)
        graph = lower_first_order_system_graph(first_order, name="two_groups")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"a": 1.0, "b": 2.0},
            input_values={"u": 1.0, "v": 2.0},
        )
        self.assertIn("Subsystem", {spec["type"] for spec in model["blocks"].values()})

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

    def test_atan2_min_max_and_sat_graph_map_to_backend_blocks(self) -> None:
        equations = translate_latex(r"\dot{x}=\atan2(u,x)+\min(x,u)+\max(x,b)+\sat(u,u_{min},u_{max})")
        extraction = extract_states(
            equations,
            mode="configured",
            symbol_config={"u": "input", "b": "parameter", "u_min": "parameter", "u_max": "parameter"},
        )
        first_order = build_first_order_system(equations, extraction=extraction)
        graph = lower_first_order_system_graph(first_order, name="multiarg_functions")
        model = graph_to_simulink_model(
            graph,
            state_names=first_order["states"],
            parameter_values={"b": 0.4, "u_min": -1.0, "u_max": 1.0},
            input_mode="inport",
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("TrigonometricFunction", block_types)
        self.assertIn("MinMax", block_types)
        self.assertIn("Saturation", block_types)

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

    def test_preserved_nonlinear_dae_graph_maps_to_algebraic_constraint_blocks(self) -> None:
        analysis = analyze_state_extraction(
            translate_latex("\n".join([r"\dot{x}=-z", r"z+\sin(z)-x=0"])),
            mode="strict",
        )
        graph = lower_semi_explicit_dae_graph(analysis.dae_system, name="nonlinear_dae")
        model = graph_to_simulink_model(
            graph,
            state_names=["x", "z"],
            initial_conditions={"x": 0.2},
            algebraic_initial_conditions={"z": 0.2},
        )
        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("AlgebraicConstraint", block_types)
        self.assertEqual([entry["name"] for entry in model["outputs"]], ["x", "z"])


if __name__ == "__main__":
    unittest.main()
