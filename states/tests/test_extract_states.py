from __future__ import annotations

import unittest
from unittest.mock import patch

from latex_frontend import symbols as frontend_symbols
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex
from pipeline.normalized_problem import CanonicalEquation, NormalizedProblem
from states import extract_states as extract_states_module
from states.extract_states import analyze_normalized_problem, analyze_state_extraction, extract_states


class ExtractStatesTests(unittest.TestCase):
    def test_mass_spring_state_extraction(self) -> None:
        result = extract_states(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u"))
        self.assertEqual(list(result.states), ["x", "x_dot"])
        self.assertEqual(list(result.inputs), ["u"])
        self.assertEqual(list(result.parameters), ["c", "k", "m"])
        self.assertEqual(result.symbol_metadata["x_dot"].role, "derivative_derived_state")

    def test_algebraic_helper_definitions_are_inlined_before_symbol_classification(self) -> None:
        result = extract_states(
            translate_latex(
                "\n".join(
                    [
                        "u=kx",
                        r"m\ddot{x}+c\dot{x}=u",
                    ]
                )
            )
        )
        self.assertEqual(list(result.states), ["x", "x_dot"])
        self.assertEqual(list(result.inputs), [])
        self.assertEqual(list(result.parameters), ["c", "k", "m"])
        self.assertNotIn("u", result.symbol_metadata)

    def test_reducible_semi_explicit_dae_eliminates_algebraic_variable_before_classification(self) -> None:
        result = extract_states(
            translate_latex(
                "\n".join(
                    [
                        "y-x=0",
                        r"\dot{x}=-y",
                    ]
                )
            )
        )
        self.assertEqual(list(result.states), ["x"])
        self.assertEqual(list(result.inputs), [])
        self.assertEqual(list(result.parameters), [])
        self.assertNotIn("y", result.symbol_metadata)

    def test_ambiguous_input_parameter_split_raises(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            extract_states(translate_latex(r"\dot{x}=ab"))

    def test_analyze_normalized_problem_uses_declared_symbol_metadata(self) -> None:
        equation = translate_latex(r"\dot{x}=-ax+u")[0]
        problem = NormalizedProblem(
            ir_version="1",
            source_type="matlab_equation_text",
            source_metadata={},
            time_variable="tau",
            states=("x",),
            algebraics=(),
            inputs=("u",),
            parameters=("a",),
            equations=(
                CanonicalEquation.from_equation_node(
                    equation,
                    original_text="xdot = -a*x + u",
                ),
            ),
            assumptions={},
            derivative_order_info={"x": 1},
            canonical_form_metadata={},
        )

        analysis = analyze_normalized_problem(problem)

        self.assertEqual(analysis.extraction.inputs, ("u",))
        self.assertEqual(analysis.extraction.parameters, ("a",))
        self.assertEqual(analysis.extraction.independent_variable, "tau")

    def test_analyze_state_extraction_falls_back_when_derivative_solver_rejects(self) -> None:
        equations = translate_latex(r"\dot{x}=-au")

        with patch(
            "canonicalize.solve_for_derivatives.solve_for_highest_derivatives",
            side_effect=frontend_symbols.DeterministicCompileError("no solved reuse"),
        ):
            analysis = analyze_state_extraction(
                equations,
                mode="configured",
                symbol_config={"a": "parameter", "u": "input"},
            )

        self.assertIsNone(analysis.solved_derivatives)
        self.assertEqual(analysis.extraction.inputs, ("u",))


if __name__ == "__main__":
    unittest.main()
