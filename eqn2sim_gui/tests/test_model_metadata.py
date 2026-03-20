from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eqn2sim_gui.model_metadata import (
    GuiModelMetadata,
    build_runtime_override_from_gui,
    extract_symbol_inventory,
    gui_symbols_to_symbol_config,
    save_gui_metadata,
    validate_gui_symbol_payload,
)
from latex_frontend.symbols import DeterministicCompileError
from latex_frontend.translator import translate_latex


class GuiModelMetadataTests(unittest.TestCase):
    def test_inventory_handles_multi_letter_symbols(self) -> None:
        inventory, state_chain, derivative_orders = extract_symbol_inventory(
            translate_latex(r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive")
        )
        self.assertEqual([entry.name for entry in inventory], ["F_drive", "c_damper", "k_spring", "m_cart", "x_cart"])
        self.assertEqual(state_chain, ("x_cart", "x_cart_dot"))
        self.assertEqual(derivative_orders, {"x_cart": 2})

    def test_validate_gui_symbol_payload_requires_derivative_symbols_to_be_states(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            validate_gui_symbol_payload(
                {"x_cart": {"role": "parameter"}},
                {"x_cart": 2},
            )

    def test_runtime_override_builds_constant_inputs_and_parameter_values(self) -> None:
        runtime = build_runtime_override_from_gui(
            {
                "m_cart": {"role": "parameter", "value": 2.0},
                "F_drive": {"role": "input", "value": 1.5, "input_kind": "constant"},
            },
            {"x_cart": 1.0, "x_cart_dot": 0.0},
            {"t_start": "0.0", "t_stop": "5.0", "sample_count": "125"},
        )
        self.assertEqual(runtime["parameter_values"], {"m_cart": 2.0})
        self.assertEqual(runtime["input_values"], {"F_drive": 1.5})
        self.assertEqual(runtime["initial_conditions"], {"x_cart": 1.0, "x_cart_dot": 0.0})
        self.assertEqual(runtime["t_span"], [0.0, 5.0])
        self.assertEqual(runtime["sample_count"], 125)

    def test_nonconstant_gui_inputs_raise_cleanly(self) -> None:
        with self.assertRaises(DeterministicCompileError):
            build_runtime_override_from_gui(
                {"u": {"role": "input", "value": 1.0, "input_kind": "function"}},
                {"x": 0.0},
            )

    def test_runtime_override_can_treat_inport_values_as_constant_for_preview(self) -> None:
        runtime = build_runtime_override_from_gui(
            {"u": {"role": "input", "value": 1.0, "input_kind": "inport"}},
            {"x": 0.0},
            preview_inports_as_constant=True,
        )
        self.assertEqual(runtime["input_values"], {"u": 1.0})

    def test_gui_symbol_config_maps_nonstate_roles_only(self) -> None:
        config = gui_symbols_to_symbol_config(
            {
                "x": {"role": "state"},
                "F": {"role": "input"},
                "m": {"role": "parameter"},
            }
        )
        self.assertEqual(config, {"F": "input", "m": "parameter"})

    def test_metadata_save_round_trip_writes_json(self) -> None:
        metadata = GuiModelMetadata(
            latex=r"\dot{x}=-ax+u",
            normalized_latex=r"\dot{x}=-ax+u",
            equations=["D1_x = u - a*x"],
            symbols={"x": {"role": "state"}, "a": {"role": "parameter"}, "u": {"role": "input"}},
            initial_conditions={"x": 0.0},
            extracted_states=["x"],
            derivative_orders={"x": 1},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_gui_metadata(Path(temp_dir) / "gui_metadata.json", metadata)
            self.assertTrue(path.exists())
            self.assertIn('"latex": "\\\\dot{x}=-ax+u"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
