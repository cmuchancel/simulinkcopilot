from __future__ import annotations

import unittest

import sympy

from backend.descriptor_to_simulink import DescriptorToSimulinkLowerer, descriptor_to_simulink_model
from canonicalize.descriptor_system import build_descriptor_system_from_dae
from ir.equation_dict import matrix_to_dict
from latex_frontend.translator import translate_latex
from latex_frontend.symbols import DeterministicCompileError
from states.extract_states import analyze_state_extraction


class DescriptorToSimulinkTests(unittest.TestCase):
    def _descriptor_payload(
        self,
        *,
        E,
        A,
        B=None,
        offset,
        differential_states=("x",),
        algebraic_variables=(),
        inputs=(),
        independent_variable=None,
    ):
        variables = [*differential_states, *algebraic_variables]
        B_matrix = sympy.Matrix(B) if B is not None else sympy.Matrix.zeros(len(variables), len(inputs))
        return {
            "form": "linear_descriptor",
            "states": variables,
            "variables": variables,
            "differential_states": list(differential_states),
            "algebraic_variables": list(algebraic_variables),
            "inputs": list(inputs),
            "parameters": [],
            "independent_variable": independent_variable,
            "E": matrix_to_dict(sympy.Matrix(E)),
            "A": matrix_to_dict(sympy.Matrix(A)),
            "B": matrix_to_dict(B_matrix),
            "C": matrix_to_dict(sympy.eye(len(variables))),
            "D": matrix_to_dict(sympy.Matrix.zeros(len(variables), len(inputs))),
            "offset": matrix_to_dict(sympy.Matrix(offset)),
        }

    def test_linear_semi_explicit_dae_maps_to_algebraic_constraint_block(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_dae",
            input_values={"u": 0.5},
            differential_initial_conditions={"x": 1.0},
            algebraic_initial_conditions={"y": 0.0},
        )

        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("Integrator", block_types)
        self.assertIn("AlgebraicConstraint", block_types)
        self.assertIn("Constant", block_types)
        self.assertEqual([entry["name"] for entry in model["outputs"]], ["x", "y"])

    def test_descriptor_model_uses_user_facing_names_for_inputs_and_algebraic_variables(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_names",
            input_values={"u": 1.0},
        )

        visible_names = {spec["name"] for spec in model["blocks"].values()}
        self.assertIn("u", visible_names)
        self.assertIn("x", visible_names)
        self.assertIn("y", visible_names)

    def test_descriptor_model_supports_time_varying_inputs_from_workspace(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_signal",
            input_signals={"u": {"time": [0.0, 1.0], "values": [0.0, 1.0]}},
        )

        block_types = {spec["type"] for spec in model["blocks"].values()}
        self.assertIn("FromWorkspace", block_types)
        self.assertEqual(model["workspace_variables"], {})
        from_workspace_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "FromWorkspace"]
        self.assertTrue(from_workspace_blocks[0]["params"]["VariableName"].startswith("["))

    def test_descriptor_model_uses_native_step_source_when_input_spec_is_available(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_step",
            input_specs={"u": {"kind": "step", "amplitude": 2.0, "start_time": 1.5, "bias": -0.5}},
            input_signals={"u": {"time": [0.0, 1.0], "values": [0.0, 1.0]}},
        )

        step_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "Step"]
        self.assertTrue(step_blocks)
        self.assertEqual(step_blocks[0]["name"], "u")
        self.assertEqual(step_blocks[0]["params"], {"Time": "1.5", "Before": "-0.5", "After": "1.5"})

    def test_descriptor_model_uses_native_ramp_source_when_input_spec_is_available(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_ramp",
            input_specs={"u": {"kind": "ramp", "slope": 2.0, "start_time": 1.5, "initial_output": -1.0}},
        )

        ramp_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "Ramp"]
        self.assertTrue(ramp_blocks)
        self.assertEqual(ramp_blocks[0]["params"], {"slope": "2", "start": "1.5", "InitialOutput": "-1"})

    def test_descriptor_model_uses_native_impulse_source_when_input_spec_is_available(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_impulse",
            input_specs={"u": {"kind": "impulse", "amplitude": 3.0, "start_time": 1.0, "width": 0.2, "period": 5.0}},
        )

        pulse_blocks = [spec for spec in model["blocks"].values() if spec["type"] == "PulseGenerator"]
        self.assertTrue(pulse_blocks)
        self.assertEqual(
            pulse_blocks[0]["params"],
            {"PulseType": "Time based", "Amplitude": "15", "Period": "5", "PulseWidth": "4", "PhaseDelay": "1"},
        )

    def test_descriptor_model_uses_native_saturation_source_chain_when_input_spec_is_available(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_sat",
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

    def test_descriptor_model_uses_native_sum_source_chain_when_input_spec_is_available(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_sum",
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

    def test_descriptor_model_uses_square_and_repeating_sequence_sources(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        square_model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_square",
            input_specs={"u": {"kind": "square", "amplitude": 2.0, "frequency": 3.0, "phase": 0.2, "bias": -1.0}},
        )
        square_types = [spec["type"] for spec in square_model["blocks"].values()]
        self.assertIn("SineWave", square_types)
        self.assertIn("Sign", square_types)

        saw_model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_saw",
            input_specs={"u": {"kind": "triangle", "amplitude": 1.0, "frequency": 2.0, "phase": 0.3, "bias": 0.0}},
        )
        saw_types = [spec["type"] for spec in saw_model["blocks"].values()]
        self.assertIn("RepeatingSequence", saw_types)
        self.assertIn("TransportDelay", saw_types)

    def test_descriptor_model_uses_piecewise_dead_zone_random_and_composite_sources(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        piecewise_model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_piecewise",
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
        piecewise_types = [spec["type"] for spec in piecewise_model["blocks"].values()]
        self.assertIn("Switch", piecewise_types)
        self.assertIn("RelationalOperator", piecewise_types)
        self.assertIn("Clock", piecewise_types)

        ops_model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_ops",
            input_specs={
                "u": {
                    "kind": "sum",
                    "terms": [
                        {"kind": "dead_zone", "input": {"kind": "sine", "amplitude": 1.0, "frequency": 2.0, "phase": 0.0, "bias": 0.0}, "lower_limit": -0.5, "upper_limit": 0.5},
                        {"kind": "random_number", "minimum": -1.0, "maximum": 1.0, "seed": 11, "sample_time": 0.1},
                        {
                            "kind": "product",
                            "terms": [
                                {"kind": "exp", "input": {"kind": "product", "terms": [{"kind": "constant", "value": -2.0}, {"kind": "time"}]}},
                                {"kind": "sine", "amplitude": 1.0, "frequency": 1.0, "phase": 0.0, "bias": 0.0},
                            ],
                        },
                    ],
                }
            },
        )
        ops_types = [spec["type"] for spec in ops_model["blocks"].values()]
        self.assertIn("DeadZone", ops_types)
        self.assertIn("UniformRandomNumber", ops_types)
        self.assertIn("MathFunction", ops_types)
        self.assertIn("Product", ops_types)

    def test_descriptor_model_uses_native_function_blocks_before_expression_fallback(self) -> None:
        equations = translate_latex(
            "\n".join(
                [
                    r"\dot{x}+y=u",
                    "x+y=1",
                ]
            )
        )
        analysis = analyze_state_extraction(equations, mode="configured", symbol_config={"u": "input"})
        descriptor = build_descriptor_system_from_dae(analysis.dae_system, analysis.extraction)

        model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_expression_native",
            input_specs={"u": {"kind": "expression", "expression": "atan(t)", "time_variable": "t"}},
        )

        block_types = [spec["type"] for spec in model["blocks"].values()]
        self.assertIn("TrigonometricFunction", block_types)
        self.assertIn("Clock", block_types)
        self.assertNotIn("FromWorkspace", block_types)
        self.assertNotIn("MATLABFunction", block_types)

        fallback_model = descriptor_to_simulink_model(
            descriptor,
            name="descriptor_expression_fallback",
            input_specs={"u": {"kind": "expression", "expression": "erf(t)", "time_variable": "t"}},
        )
        fallback_types = [spec["type"] for spec in fallback_model["blocks"].values()]
        self.assertIn("MATLABFunction", fallback_types)
        self.assertIn("Clock", fallback_types)
        self.assertNotIn("FromWorkspace", fallback_types)
        function_blocks = [spec for spec in fallback_model["blocks"].values() if spec["type"] == "MATLABFunction"]
        self.assertIn("erf(t)", function_blocks[0]["metadata"]["matlab_function_script"])

    def test_descriptor_lowerer_rejects_invalid_shapes_and_coefficients(self) -> None:
        with self.assertRaisesRegex(DeterministicCompileError, "requires a linear_descriptor system"):
            DescriptorToSimulinkLowerer({"form": "wrong"}, "demo")

        with self.assertRaisesRegex(DeterministicCompileError, "one equation row per variable"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[1]], A=[[0], [0]], B=[[0], [0]], inputs=("u",), offset=[[0], [0]]),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "E matrix width must match"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[1, 0]], A=[[0]], B=[[0]], inputs=("u",), offset=[[0]]),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "A matrix width must match"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[1]], A=[[0, 0]], B=[[0]], inputs=("u",), offset=[[0]]),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "B matrix row count must match"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[1]], A=[[0]], B=[[0], [0]], offset=[[0]]),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "offset must be a column vector"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[1]], A=[[0]], B=[[0]], inputs=("u",), offset=[[0, 1]]),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "unsupported symbolic coefficients"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[sympy.Symbol("k")]], A=[[0]], B=[[0]], inputs=("u",), offset=[[0]]),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "time-invariant descriptor systems only"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(E=[[1]], A=[[0]], B=[[0]], inputs=("u",), offset=[[0]], independent_variable="t"),
                "demo",
            )

    def test_descriptor_lowerer_helper_paths_cover_empty_terms_and_missing_inputs(self) -> None:
        lowerer = DescriptorToSimulinkLowerer(
            self._descriptor_payload(E=[[1]], A=[[0]], B=[[0]], inputs=("u",), offset=[[0]]),
            "demo",
            input_values={"u": 0.0},
        )
        self.assertEqual(lowerer._match_algebraic_rows(), {})
        self.assertEqual(lowerer._sum_terms([], trace_expression="zero", layer_hint=0)[1], "1")

        source = lowerer.add_block("const", "Constant", name="const")
        self.assertEqual(source, "const")
        self.assertEqual(lowerer.add_block("const", "Constant", name="ignored"), "const")
        self.assertEqual(lowerer._sum_terms([(("const", "1"), "const")], trace_expression="const", layer_hint=0), ("const", "1"))

        missing_input_lowerer = DescriptorToSimulinkLowerer(
            self._descriptor_payload(E=[[1]], A=[[0]], B=[[1]], offset=[[0]], inputs=("u",)),
            "demo",
        )
        with self.assertRaisesRegex(DeterministicCompileError, "No numeric value or input signal provided"):
            missing_input_lowerer._materialize_inputs()

    def test_descriptor_lowerer_rejects_bad_row_assignment_rhs_and_output_name(self) -> None:
        recursive_assignment = DescriptorToSimulinkLowerer(
            self._descriptor_payload(
                E=[[1, 0, 0], [0, 0, 0], [0, 0, 0]],
                A=[[0, 0, 0], [0, 1, 1], [0, 1, 0]],
                B=[[0], [0], [0]],
                inputs=("u",),
                offset=[[0], [0], [0]],
                algebraic_variables=("z1", "z2"),
            ),
            "demo",
        )
        self.assertEqual(recursive_assignment.algebraic_row_assignment, {1: 2, 2: 1})

        ambiguous = DescriptorToSimulinkLowerer(
            self._descriptor_payload(
                E=[[1, 0], [0, 0]],
                A=[[0, 1], [1, 1]],
                B=[[0], [0]],
                inputs=("u",),
                offset=[[0], [0]],
                algebraic_variables=("z",),
            ),
            "demo",
        )
        self.assertEqual(ambiguous.algebraic_row_assignment, {1: 1})

        with self.assertRaisesRegex(DeterministicCompileError, "lacks a deterministic row-to-variable assignment"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(
                    E=[[1, 0], [0, 0]],
                    A=[[0, 1], [1, 0]],
                    B=[[0], [0]],
                    inputs=("u",),
                    offset=[[0], [0]],
                    algebraic_variables=("z",),
                ),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "lacks a deterministic row-to-variable assignment"):
            DescriptorToSimulinkLowerer(
                self._descriptor_payload(
                    E=[[1, 0, 0], [0, 0, 0], [0, 0, 0]],
                    A=[[0, 0, 0], [0, 1, 0], [0, 1, 0]],
                    B=[[0], [0], [0]],
                    inputs=("u",),
                    offset=[[0], [0], [0]],
                    algebraic_variables=("z1", "z2"),
                ),
                "demo",
            )

        with self.assertRaisesRegex(DeterministicCompileError, "Descriptor differential rows must isolate"):
            bad_rhs = DescriptorToSimulinkLowerer(
                self._descriptor_payload(
                    E=[[1, 1], [0, 1]],
                    A=[[0, 0], [0, 0]],
                    B=[[0], [0]],
                    inputs=("u",),
                    offset=[[0], [0]],
                    differential_states=("x", "y"),
                ),
                "demo",
            )
            bad_rhs.sources = {"x": ("int_x", "1"), "y": ("int_y", "1")}
            bad_rhs._build_differential_rhs()

        lowerer = DescriptorToSimulinkLowerer(
            self._descriptor_payload(E=[[1]], A=[[0]], B=[[0]], inputs=("u",), offset=[[0]]),
            "demo",
            input_values={"u": 0.0},
        )
        lowerer._materialize_differential_states()
        lowerer._build_algebraic_constraints()
        with self.assertRaisesRegex(DeterministicCompileError, "Descriptor output 'missing' is not available"):
            lowerer.lower(output_names=["missing"])


if __name__ == "__main__":
    unittest.main()
