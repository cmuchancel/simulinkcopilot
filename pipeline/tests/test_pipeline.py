from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
import tempfile
from contextlib import redirect_stdout
from unittest import mock

import pytest

from eqn2sim_gui.model_metadata import GuiModelMetadata
from pipeline.gui_export import export_results_to_gui_run
from pipeline.run_pipeline import DEFAULT_SIMULINK_OUTPUT_DIR, _resolved_simulink_output_dir, main, run_pipeline
from pipeline.verbose_artifacts import write_verbose_artifacts
from repo_paths import EXAMPLES_ROOT


class PipelineTests(unittest.TestCase):
    def test_mass_spring_pipeline(self) -> None:
        result = run_pipeline(EXAMPLES_ROOT / "mass_spring_damper.tex")
        self.assertEqual(result["extraction"].states, ("x", "x_dot"))
        self.assertTrue(result["comparison"]["passes"])
        self.assertIsNotNone(result["graph"])

    def test_nonlinear_pipeline_skips_state_space_comparison(self) -> None:
        result = run_pipeline(EXAMPLES_ROOT / "nonlinear_pendulum.tex")
        self.assertFalse(result["linearity"]["is_linear"])
        self.assertIsNone(result["state_space"])
        self.assertIsNone(result["comparison"])

    @pytest.mark.matlab
    @pytest.mark.slow
    def test_nonlinear_pipeline_allows_simulink_validation(self) -> None:
        result = run_pipeline(
            EXAMPLES_ROOT / "nonlinear_pendulum.tex",
            run_simulink=True,
        )
        self.assertFalse(result["linearity"]["is_linear"])
        self.assertIsNone(result["state_space"])
        self.assertIsNotNone(result["simulink_result"])
        self.assertIsNotNone(result["simulink_validation"])
        self.assertIsNone(result["simulink_validation"]["vs_state_space"])
        self.assertTrue(result["simulink_validation"]["passes"])

    def test_runtime_override_changes_ad_hoc_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "decay.tex"
            input_path.write_text(r"\dot{x}=-ax", encoding="utf-8")
            result = run_pipeline(
                input_path,
                runtime_override={
                    "parameter_values": {"a": 2.0},
                    "initial_conditions": {"x": 1.0},
                    "t_span": [0.0, 1.0],
                    "sample_count": 25,
                },
            )
        self.assertEqual(result["runtime"]["parameter_values"]["a"], 2.0)
        self.assertEqual(result["runtime"]["initial_conditions"]["x"], 1.0)
        self.assertAlmostEqual(float(result["ode_result"]["states"][0, 0]), 1.0)
        self.assertLess(float(result["ode_result"]["states"][-1, 0]), 1.0)

    def test_pipeline_accepts_explicit_symbol_metadata_for_arbitrary_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "cart.tex"
            input_path.write_text(
                r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive",
                encoding="utf-8",
            )
            result = run_pipeline(
                input_path,
                classification_mode="configured",
                symbol_config={
                    "m_cart": "parameter",
                    "c_damper": "parameter",
                    "k_spring": "parameter",
                    "F_drive": "input",
                },
                runtime_override={
                    "parameter_values": {"m_cart": 2.0, "c_damper": 0.4, "k_spring": 8.0},
                    "initial_conditions": {"x_cart": 1.0, "x_cart_dot": 0.0},
                    "input_values": {"F_drive": 1.5},
                    "t_span": [0.0, 2.0],
                    "sample_count": 60,
                },
            )
        self.assertEqual(result["extraction"].states, ("x_cart", "x_cart_dot"))
        self.assertEqual(result["extraction"].inputs, ("F_drive",))
        self.assertEqual(result["extraction"].parameters, ("c_damper", "k_spring", "m_cart"))
        self.assertLess(float(result["ode_result"]["states"][-1, 0]), 1.0)

    def test_pipeline_inlines_algebraic_helpers_before_runtime_symbol_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "helper_driven.tex"
            input_path.write_text(
                "\n".join(
                    [
                        "u=-kx",
                        r"m\ddot{x}+c\dot{x}=u",
                    ]
                ),
                encoding="utf-8",
            )
            result = run_pipeline(
                input_path,
                runtime_override={
                    "parameter_values": {"m": 2.0, "c": 0.4, "k": 8.0},
                    "initial_conditions": {"x": 1.0, "x_dot": 0.0},
                    "t_span": [0.0, 2.0],
                    "sample_count": 60,
                },
            )
        self.assertEqual(result["extraction"].states, ("x", "x_dot"))
        self.assertEqual(result["extraction"].inputs, ())
        self.assertEqual(result["extraction"].parameters, ("c", "k", "m"))
        self.assertLess(float(result["ode_result"]["states"][-1, 0]), 1.0)

    def test_pipeline_reduces_reducible_semi_explicit_dae_before_ode_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "semi_explicit_dae.tex"
            input_path.write_text(
                "\n".join(
                    [
                        "y-x=0",
                        r"\dot{x}=-y",
                    ]
                ),
                encoding="utf-8",
            )
            result = run_pipeline(
                input_path,
                runtime_override={
                    "initial_conditions": {"x": 1.0},
                    "t_span": [0.0, 1.0],
                    "sample_count": 30,
                },
            )
        self.assertEqual(result["extraction"].states, ("x",))
        self.assertEqual(result["extraction"].inputs, ())
        self.assertEqual(result["extraction"].parameters, ())
        self.assertTrue(result["comparison"]["passes"])
        self.assertLess(float(result["ode_result"]["states"][-1, 0]), 1.0)

    def test_pipeline_supports_declared_independent_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "time_varying.tex"
            input_path.write_text(
                r"\dot{x}=-t x+u",
                encoding="utf-8",
            )
            result = run_pipeline(
                input_path,
                classification_mode="configured",
                symbol_config={
                    "t": "independent_variable",
                    "u": "input",
                },
                runtime_override={
                    "initial_conditions": {"x": 1.0},
                    "input_values": {"u": 0.0},
                    "t_span": [0.0, 1.0],
                    "sample_count": 30,
                },
            )
        self.assertEqual(result["extraction"].independent_variable, "t")
        self.assertEqual(result["extraction"].inputs, ("u",))
        self.assertEqual(result["extraction"].parameters, ())
        self.assertIsNotNone(result["state_space"])
        self.assertTrue(result["comparison"]["passes"])

    def test_pipeline_handles_multi_input_linear_systems(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "mimo.tex"
            input_path.write_text(
                r"\dot{x}=a x+b u_1+c u_2",
                encoding="utf-8",
            )
            result = run_pipeline(
                input_path,
                classification_mode="configured",
                symbol_config={
                    "a": "parameter",
                    "b": "parameter",
                    "c": "parameter",
                    "u_1": "input",
                    "u_2": "input",
                },
                runtime_override={
                    "parameter_values": {"a": -0.4, "b": 2.0, "c": -1.0},
                    "initial_conditions": {"x": 0.25},
                    "input_values": {"u_1": 1.5, "u_2": -0.5},
                    "t_span": [0.0, 4.0],
                    "t_eval": [0.0, 0.5, 1.0, 2.0, 4.0],
                },
            )
            self.assertEqual(result["extraction"].inputs, ("u_1", "u_2"))
            self.assertIsNotNone(result["state_space"])
            self.assertTrue(result["comparison"]["passes"])

    def test_default_simulink_output_dir_is_workspace_bedillion_demo(self) -> None:
        self.assertEqual(_resolved_simulink_output_dir(None), DEFAULT_SIMULINK_OUTPUT_DIR.resolve())

    def test_cli_accepts_inline_runtime_overrides_and_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "cart_pendulum.tex"
            report_path = Path(temp_dir) / "report.json"
            input_path.write_text(
                "\n".join(
                    [
                        r"(m_1 + m_2)\ddot{x} + \frac{m_2 l}{2}\cos(\theta)\ddot{\theta} - \frac{m_2 l}{2}\sin(\theta)\dot{\theta}^2 + kx = 0",
                        r"\frac{m_2 l}{2}\cos(\theta)\ddot{x} + \frac{1}{4}(m_2 l^2 + 4I)\ddot{\theta} + \frac{m_2 g l}{2}\sin(\theta) = 0",
                    ]
                ),
                encoding="utf-8",
            )
            argv = [
                "run_pipeline.py",
                "--input",
                str(input_path),
                "--no-simulink",
                "--skip-sim",
                "--parameter",
                "m_1=10.0",
                "--parameter",
                "m_2=2.0",
                "--parameter",
                "l=1.0",
                "--parameter",
                "I=0.17",
                "--parameter",
                "g=9.81",
                "--parameter",
                "k=100.0",
                "--initial",
                "x=1.0",
                "--initial",
                "x_dot=0.0",
                "--initial",
                "theta=0.7853981633974483",
                "--initial",
                "theta_dot=0.0",
                "--state",
                "theta",
                "--state",
                "theta_dot",
                "--state",
                "x",
                "--state",
                "x_dot",
                "--t-span",
                "0.0",
                "10.0",
                "--sample-count",
                "100",
                "--report-json",
                str(report_path),
            ]
            with mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                exit_code = main()
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["extraction"]["states"], ["theta", "theta_dot", "x", "x_dot"])
        self.assertEqual(report["runtime"]["parameter_values"]["m_1"], 10.0)
        self.assertEqual(report["runtime"]["initial_conditions"]["theta"], 0.7853981633974483)

    def test_cli_accepts_equations_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            argv = [
                "run_pipeline.py",
                "--equations",
                "\n".join(
                    [
                        r"(m_1 + m_2)\ddot{x} + \frac{m_2 l}{2}\cos(\theta)\ddot{\theta} - \frac{m_2 l}{2}\sin(\theta)\dot{\theta}^2 + kx = 0",
                        r"\frac{m_2 l}{2}\cos(\theta)\ddot{x} + \frac{1}{4}(m_2 l^2 + 4I)\ddot{\theta} + \frac{m_2 g l}{2}\sin(\theta) = 0",
                    ]
                ),
                "--equations-name",
                "cart_pendulum_inline",
                "--no-simulink",
                "--skip-sim",
                "--parameter",
                "m_1=10.0",
                "--parameter",
                "m_2=2.0",
                "--parameter",
                "l=1.0",
                "--parameter",
                "I=0.17",
                "--parameter",
                "g=9.81",
                "--parameter",
                "k=100.0",
                "--initial",
                "x=1.0",
                "--initial",
                "x_dot=0.0",
                "--initial",
                "theta=0.7853981633974483",
                "--initial",
                "theta_dot=0.0",
                "--state",
                "theta",
                "--state",
                "theta_dot",
                "--state",
                "x",
                "--state",
                "x_dot",
                "--report-json",
                str(report_path),
            ]
            with mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                exit_code = main()
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertTrue(report["source_path"].endswith("cart_pendulum_inline.tex"))
        self.assertEqual(report["extraction"]["states"], ["theta", "theta_dot", "x", "x_dot"])

    def test_cli_accepts_inline_symbol_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "cart.tex"
            report_path = Path(temp_dir) / "report.json"
            input_path.write_text(
                r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive",
                encoding="utf-8",
            )
            argv = [
                "run_pipeline.py",
                "--input",
                str(input_path),
                "--no-simulink",
                "--skip-sim",
                "--symbol-role",
                "m_cart=parameter",
                "--symbol-role",
                "c_damper=parameter",
                "--symbol-role",
                "k_spring=parameter",
                "--symbol-role",
                "F_drive=input",
                "--parameter",
                "m_cart=2.0",
                "--parameter",
                "c_damper=0.4",
                "--parameter",
                "k_spring=8.0",
                "--input-value",
                "F_drive=1.5",
                "--initial",
                "x_cart=1.0",
                "--initial",
                "x_cart_dot=0.0",
                "--t-span",
                "0.0",
                "2.0",
                "--sample-count",
                "60",
                "--report-json",
                str(report_path),
            ]
            with mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                exit_code = main()
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["extraction"]["states"], ["x_cart", "x_cart_dot"])
        self.assertEqual(report["extraction"]["inputs"], ["F_drive"])
        self.assertEqual(report["extraction"]["parameters"], ["c_damper", "k_spring", "m_cart"])

    def test_gui_export_writes_reopenable_run_bundle(self) -> None:
        result = run_pipeline(EXAMPLES_ROOT / "mass_spring_damper.tex")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_model = temp_root / "mass_spring_demo.slx"
            source_model.write_text("demo", encoding="utf-8")
            result["simulink_model"] = {"name": "demo_model", "blocks": {}, "connections": [], "outputs": []}
            result["simulink_result"] = {
                **result["ode_result"],
                "model_name": "demo_model",
                "model_file": str(source_model),
            }

            export_info = export_results_to_gui_run(
                result,
                raw_latex=Path(result["source_path"]).read_text(encoding="utf-8"),
                gui_report_root=temp_root / "gui_runs",
            )

            run_dir = Path(export_info["artifact_dir"])
            self.assertTrue((run_dir / "gui_metadata.json").exists())
            self.assertTrue((run_dir / "validated_model_spec.json").exists())
            self.assertTrue((run_dir / "simulink_model_dict.json").exists())
            self.assertTrue((run_dir / "mass_spring_demo.slx").exists())
            self.assertTrue((run_dir / "state_trajectory_data.json").exists())
            self.assertTrue((run_dir / "state_trajectory_plot.svg").exists())

            payload = json.loads((run_dir / "gui_metadata.json").read_text(encoding="utf-8"))
            metadata = GuiModelMetadata(
                latex=payload["latex"],
                normalized_latex=payload["normalized_latex"],
                equations=payload["equations"],
                symbols=payload["symbols"],
                initial_conditions=payload["initial_conditions"],
                extracted_states=payload["extracted_states"],
                derivative_orders=payload["derivative_orders"],
            )
            self.assertEqual(metadata.extracted_states, ["x", "x_dot"])
            self.assertEqual(metadata.symbols["x"]["role"], "state")
            self.assertEqual(metadata.symbols["m"]["role"], "parameter")

    def test_verbose_artifacts_are_written(self) -> None:
        import tempfile

        result = run_pipeline(EXAMPLES_ROOT / "mass_spring_damper.tex")
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = write_verbose_artifacts(result, temp_dir)
            self.assertTrue((Path(temp_dir) / "input_equations.tex").exists())
            self.assertTrue((Path(temp_dir) / "normalized_equations.tex").exists())
            self.assertTrue((Path(temp_dir) / "token_stream.json").exists())
            self.assertTrue((Path(temp_dir) / "parsed_trees.json").exists())
            self.assertTrue((Path(temp_dir) / "equation_dicts.json").exists())
            self.assertTrue((Path(temp_dir) / "extraction.json").exists())
            self.assertTrue((Path(temp_dir) / "residual_equations.txt").exists())
            self.assertTrue((Path(temp_dir) / "solved_derivatives.txt").exists())
            self.assertTrue((Path(temp_dir) / "first_order_system.txt").exists())
            self.assertTrue((Path(temp_dir) / "explicit_form.json").exists())
            self.assertTrue((Path(temp_dir) / "linearity.json").exists())
            self.assertTrue((Path(temp_dir) / "runtime.json").exists())
            self.assertTrue((Path(temp_dir) / "intermediate_equations.txt").exists())
            self.assertTrue((Path(temp_dir) / "state_space.txt").exists())
            self.assertTrue((Path(temp_dir) / "simulation_plot.png").exists())
            self.assertTrue((Path(temp_dir) / "walkthrough.md").exists())
            walkthrough = (Path(temp_dir) / "walkthrough.md").read_text(encoding="utf-8")
            self.assertIn("## 1. Input equations", walkthrough)
            self.assertIn("This is what you inputted.", walkthrough)
            self.assertIn("This is what we converted it to before tokenization.", walkthrough)
            self.assertIn("output_dir", manifest)

    def test_verbose_artifacts_write_walkthrough_when_simulink_image_succeeds(self) -> None:
        result = run_pipeline(EXAMPLES_ROOT / "mass_spring_damper.tex")
        result["simulink_result"] = {
            **result["ode_result"],
            "model_name": "demo_model",
            "model_file": "/tmp/demo_model.slx",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch(
                "pipeline.verbose_artifacts._render_simulink_model_image",
                return_value=str(Path(temp_dir) / "simulink_model.png"),
            ):
                manifest = write_verbose_artifacts(result, temp_dir, matlab_engine=object())
            self.assertEqual(manifest["files"]["simulink_model_note"], None)
            self.assertEqual(manifest["files"]["simulink_model_image"], str(Path(temp_dir) / "simulink_model.png"))
            walkthrough = (Path(temp_dir) / "walkthrough.md").read_text(encoding="utf-8")
            self.assertIn("Simulink model image artifact", walkthrough)


if __name__ == "__main__":
    unittest.main()
