from __future__ import annotations

import unittest

from backend.descriptor_to_simulink import descriptor_to_simulink_model
from canonicalize.descriptor_system import build_descriptor_system_from_dae
from latex_frontend.translator import translate_latex
from states.extract_states import analyze_state_extraction


class DescriptorToSimulinkTests(unittest.TestCase):
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
        self.assertTrue(model["workspace_variables"])


if __name__ == "__main__":
    unittest.main()
