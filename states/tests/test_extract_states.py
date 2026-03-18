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

    def test_ambiguous_input_parameter_split_raises(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            extract_states(translate_latex(r"\dot{x}=ab"))


if __name__ == "__main__":
    unittest.main()
