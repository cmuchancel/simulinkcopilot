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
        self.assertTrue(model["workspace_variables"])

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
