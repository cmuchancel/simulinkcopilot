from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from latex_frontend_v2.symbols import DeterministicCompileError
from latex_frontend_v2.translator import translate_latex
from states_v2.extract_states import extract_states


class SymbolClassificationTests(unittest.TestCase):
    def test_mass_spring_metadata_is_deterministic(self) -> None:
        result = extract_states(translate_latex(r"m\ddot{x}+c\dot{x}+kx=u"))
        self.assertEqual(result.symbol_metadata["x"].role, "state_candidate")
        self.assertEqual(result.symbol_metadata["x_dot"].role, "derivative_derived_state")
        self.assertEqual(result.symbol_metadata["u"].role, "input")
        self.assertEqual(result.symbol_metadata["m"].role, "parameter")

    def test_multiple_external_symbols_in_pure_product_raise_in_strict_mode(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            extract_states(translate_latex(r"\dot{x}=ab"))

    def test_configured_mode_can_resolve_ambiguous_product(self) -> None:
        result = extract_states(
            translate_latex(r"\dot{x}=ab"),
            mode="configured",
            symbol_config={"a": "parameter", "b": "input"},
        )
        self.assertEqual(result.inputs, ("b",))
        self.assertEqual(result.parameters, ("a",))

    def test_configured_mode_requires_explicit_pure_forcing_symbols(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            extract_states(
                translate_latex(r"\dot{x}=u-y"),
                mode="configured",
                symbol_config={"u": "input"},
            )

    def test_configured_mode_accepts_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "symbols.json"
            config_path.write_text(json.dumps({"f": "input", "m": "parameter"}), encoding="utf-8")
            result = extract_states(
                translate_latex(r"m\dot{x}=f"),
                mode="configured",
                symbol_config=config_path,
            )
        self.assertEqual(result.inputs, ("f",))
        self.assertEqual(result.parameters, ("m",))

    def test_configured_mode_resolves_function_wrapped_symbols(self) -> None:
        result = extract_states(
            translate_latex(r"\dot{x}=\exp(-ax)+\ln(b)+u"),
            mode="configured",
            symbol_config={"a": "parameter", "b": "parameter", "u": "input"},
        )
        self.assertEqual(result.inputs, ("u",))
        self.assertEqual(result.parameters, ("a", "b"))

    def test_multi_equation_shared_parameters_are_identified(self) -> None:
        result = extract_states(
            translate_latex("\\dot{x}=v\nm\\dot{v}+c v + kx = u"),
        )
        self.assertEqual(result.inputs, ("u",))
        self.assertEqual(result.parameters, ("c", "k", "m"))


if __name__ == "__main__":
    unittest.main()
