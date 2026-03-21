from __future__ import annotations

import unittest

from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex
from states.extract_states import extract_states


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


if __name__ == "__main__":
    unittest.main()
