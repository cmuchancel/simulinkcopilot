from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eqn2sim_gui.app import _extract_seeded_symbol_values_from_raw_text, create_app
from eqn2sim_gui.llm_draft import DraftModelSpec, DraftSymbol
from repo_paths import GUI_RUNS_ROOT


class Eqn2SimGuiAppTests(unittest.TestCase):
    def test_get_route_exposes_reset_and_progress_controls(self) -> None:
        app = create_app()
        app.config.update(TESTING=True)
        client = app.test_client()

        response = client.get("/")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Reset All", html)
        self.assertIn('id="working-progress-fill"', html)
        self.assertIn('data-progress-title="Generating structured output"', html)

    def test_get_route_can_load_saved_run_into_demo_browser(self) -> None:
        app = create_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            run_name = "run_20260320_101500_deadbeefcafe_abc123"
            run_dir = Path(temp_dir) / run_name
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "gui_metadata.json").write_text(
                json.dumps(
                    {
                        "latex": r"m_cart\ddot{x_cart}+k_spring x_cart=0",
                        "normalized_latex": r"m_cart\ddot{x_cart}+k_spring x_cart=0",
                        "equations": ["D2_x_cart*m_cart + k_spring*x_cart = 0"],
                        "symbols": {
                            "m_cart": {"role": "parameter", "description": "", "units": "", "value": 2.0, "input_kind": "constant"},
                            "k_spring": {"role": "parameter", "description": "", "units": "", "value": 8.0, "input_kind": "constant"},
                            "x_cart": {"role": "state", "description": "", "units": "", "value": None, "input_kind": "constant"},
                        },
                        "initial_conditions": {"x_cart": 1.0, "x_cart_dot": 0.0},
                        "extracted_states": ["x_cart", "x_cart_dot"],
                        "derivative_orders": {"x_cart": 2},
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "validated_model_spec.json").write_text("{}", encoding="utf-8")
            (run_dir / "simulink_model_dict.json").write_text("{}", encoding="utf-8")
            (run_dir / f"{run_name}.slx").write_bytes(b"fake slx")
            (run_dir / "state_trajectory_plot.svg").write_text("<svg><text>trajectory</text></svg>", encoding="utf-8")
            (run_dir / "state_trajectory_data.json").write_text(
                json.dumps(
                    {
                        "t_span": [0.0, 1.0],
                        "state_names": ["x_cart", "x_cart_dot"],
                        "series": [
                            {
                                "label": "ODE",
                                "t": [0.0, 1.0],
                                "states": {"x_cart": [1.0, 0.5], "x_cart_dot": [0.0, -0.5]},
                            },
                            {
                                "label": "Simulink",
                                "t": [0.0, 1.0],
                                "states": {"x_cart": [1.0, 0.5], "x_cart_dot": [0.0, -0.5]},
                            },
                        ],
                        "simulink_error": None,
                    }
                ),
                encoding="utf-8",
            )
            app.config.update(TESTING=True, GUI_REPORT_ROOT=temp_dir)
            client = app.test_client()

            response = client.get(f"/?run={run_name}")
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Run Browser", html)
            self.assertIn("Selected run", html)
            self.assertIn(run_name, html)
            self.assertIn("Loaded saved run", html)
            self.assertIn("name=\"symbol_role__x_cart\"", html)
            self.assertIn("Download .slx", html)
            self.assertIn("State trajectories over time", html)

    @patch("eqn2sim_gui.app.draft_model_spec_from_raw_text_with_diagnostics")
    def test_draft_route_populates_structured_output_equations_and_symbols(self, draft_mock) -> None:
        from eqn2sim_gui.llm_draft import DraftDiagnostics, DraftGenerationResult

        draft_mock.return_value = DraftGenerationResult(
            spec=DraftModelSpec(
                equations=[r"\ddot{\theta}+\frac{g}{L}\sin(\theta)=0"],
                symbols=[
                    DraftSymbol(name="theta", role="state"),
                    DraftSymbol(name="g", role="known_constant", value=9.81),
                    DraftSymbol(name="L", role="parameter"),
                ],
            ),
            diagnostics=DraftDiagnostics(mode="llm", elapsed_seconds=1.25, model="gpt-5-mini", timeout_seconds=20.0),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app()
            app.config.update(TESTING=True, GUI_DEBUG_ROOT=temp_dir)
            client = app.test_client()

            response = client.post(
                "/",
                data={"action": "draft_structured", "raw_text": "pendulum equation with gravity g and length L"},
            )
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Structured output generated in 1.2 seconds with gpt-5-mini.", html)
            self.assertIn(r"\ddot{\theta}+\frac{g}{L}\sin(\theta)=0", html)
            self.assertIn("Rendered equations", html)
            self.assertIn('name="symbol_role__theta"', html)
            self.assertIn('<option value="state" selected>state</option>', html)

    @patch("eqn2sim_gui.app.draft_model_spec_from_raw_text_with_diagnostics")
    def test_draft_route_writes_backend_debug_trace(self, draft_mock) -> None:
        from eqn2sim_gui.llm_draft import DraftDiagnostics, DraftGenerationResult

        draft_mock.return_value = DraftGenerationResult(
            spec=DraftModelSpec(equations=[r"m\ddot{x}+kx=0"], symbols=[]),
            diagnostics=DraftDiagnostics(mode="llm", elapsed_seconds=0.5, model="gpt-5-mini", timeout_seconds=21.0),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app()
            app.config.update(TESTING=True, GUI_DEBUG_ROOT=temp_dir)
            client = app.test_client()

            response = client.post(
                "/",
                data={
                    "action": "draft_structured",
                    "raw_text": "simple oscillator",
                    "debug_request_id": "abc123def456",
                },
            )
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("abc123def456", html)
            trace_path = Path(temp_dir) / "abc123def456.json"
            self.assertTrue(trace_path.exists())
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["request_id"], "abc123def456")
            self.assertEqual(payload["status"], "completed")
            stages = [event["stage"] for event in payload["events"]]
            self.assertIn("request_received", stages)
            self.assertIn("llm_draft_completed", stages)
            self.assertIn("deterministic_analysis_completed", stages)

    def test_raw_text_value_notes_are_preserved_for_symbol_defaults(self) -> None:
        seeded, preserved_count = _extract_seeded_symbol_values_from_raw_text(
            r"""
            - \(g = 9.81 \, \text{m/s}^2\)
            - \(L = 2.5 \, \text{m}\)
            - \(\phi_e = \pi R^2 \approx 1.77 \times 10^{-8} \, \text{m}^2\)
            - \(\cos\theta \approx 0.707\)
            - \(\dot{m} = 1 \times 10^{-5} \, \text{kg/s}\)
            """
        )
        self.assertEqual(preserved_count, 5)
        self.assertEqual(seeded["g"]["value"], 9.81)
        self.assertEqual(seeded["L"]["value"], 2.5)
        self.assertAlmostEqual(seeded["phi_e"]["value"], 1.77e-8)
        self.assertNotIn("cos", seeded)
        self.assertNotIn("m", seeded)

    def test_refresh_route_shows_missing_definition_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app()
            app.config.update(TESTING=True, GUI_DEBUG_ROOT=temp_dir)
            client = app.test_client()

            response = client.post(
                "/",
                data={"action": "refresh_equations", "latex": r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive"},
            )
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Deterministic symbol extraction", html)
            self.assertIn("Provide a numeric value for `F_drive`.", html)
            self.assertIn('name="state_ic__x_cart" value="0.0"', html)
            self.assertIn("Generate Simulink Model", html)
            self.assertIn("disabled", html)

    def test_refresh_route_omits_algebraically_defined_helper_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app()
            app.config.update(TESTING=True, GUI_DEBUG_ROOT=temp_dir)
            client = app.test_client()

            response = client.post(
                "/",
                data={
                    "action": "refresh_equations",
                    "latex": "\n".join(
                        [
                            "u_1=kx",
                            r"m\ddot{x}=u_1",
                        ]
                    ),
                },
            )
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn('name="symbol_role__m"', html)
            self.assertIn('name="symbol_role__k"', html)
            self.assertIn('name="symbol_role__x"', html)
            self.assertNotIn('name="symbol_role__u_1"', html)

    @patch("eqn2sim_gui.app._generate_state_trajectory_artifacts")
    @patch("eqn2sim_gui.app._generate_simulink_artifact")
    def test_generate_route_builds_artifacts_and_exposes_download(self, build_mock, trajectory_mock) -> None:
        app = create_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def fake_build(metadata, artifact_dir):
                model_dict_path = artifact_dir / "simulink_model_dict.json"
                model_file_path = artifact_dir / "run_model.slx"
                model_dict_path.write_text('{"name": "fake"}', encoding="utf-8")
                model_file_path.write_bytes(b"fake slx")
                return {
                    "model_dict_path": str(model_dict_path),
                    "model_file": str(model_file_path),
                }

            build_mock.side_effect = fake_build
            trajectory_mock.return_value = {
                "state_trajectory_svg": "<svg><text>trajectory</text></svg>",
                "state_trajectory_error": None,
                "state_trajectory_plot_path": str(output_dir / "state_trajectory_plot.svg"),
                "state_trajectory_data_path": str(output_dir / "state_trajectory_data.json"),
                "state_trajectory_summary": {
                    "state_count": 2,
                    "sample_count": 400,
                    "t_start": 0.0,
                    "t_stop": 10.0,
                    "state_names": ["x_cart", "x_cart_dot"],
                    "series_labels": ["ODE", "Simulink"],
                    "simulink_available": True,
                    "simulink_error": None,
                },
            }
            app.config.update(TESTING=True, GUI_REPORT_ROOT=temp_dir, GUI_DEBUG_ROOT=temp_dir)
            client = app.test_client()

            response = client.post(
                "/",
                data={
                    "action": "generate_model",
                    "latex": r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive",
                    "symbol_role__x_cart": "state",
                    "symbol_role__m_cart": "parameter",
                    "symbol_role__c_damper": "parameter",
                    "symbol_role__k_spring": "parameter",
                    "symbol_role__F_drive": "input",
                    "symbol_value__m_cart": "2.0",
                    "symbol_value__c_damper": "0.4",
                    "symbol_value__k_spring": "8.0",
                    "symbol_value__F_drive": "1.5",
                    "symbol_input_kind__F_drive": "inport",
                    "state_ic__x_cart": "1.0",
                    "state_ic__x_cart_dot": "0.0",
                },
            )
            html = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Simulink model ready.", html)
            self.assertIn("Download .slx", html)
            self.assertIn("State trajectories over time", html)
            created = list(output_dir.glob("run_*"))
            self.assertEqual(len(created), 1)
            self.assertTrue((created[0] / "gui_metadata.json").exists())
            self.assertTrue((created[0] / "validated_model_spec.json").exists())
            self.assertTrue((created[0] / "simulink_model_dict.json").exists())
            self.assertTrue((created[0] / "run_model.slx").exists())

    @patch("eqn2sim_gui.app._generate_state_trajectory_artifacts")
    @patch("eqn2sim_gui.app._generate_simulink_artifact")
    def test_generate_route_preserves_past_runs_for_identical_input(self, build_mock, trajectory_mock) -> None:
        app = create_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def fake_build(metadata, artifact_dir):
                model_dict_path = artifact_dir / "simulink_model_dict.json"
                model_file_path = artifact_dir / f"{artifact_dir.name}.slx"
                model_dict_path.write_text('{"name": "fake"}', encoding="utf-8")
                model_file_path.write_bytes(b"fake slx")
                return {
                    "model_dict_path": str(model_dict_path),
                    "model_file": str(model_file_path),
                }

            build_mock.side_effect = fake_build
            trajectory_mock.return_value = {
                "state_trajectory_svg": None,
                "state_trajectory_error": None,
                "state_trajectory_plot_path": None,
                "state_trajectory_data_path": None,
                "state_trajectory_summary": None,
            }
            app.config.update(TESTING=True, GUI_REPORT_ROOT=temp_dir, GUI_DEBUG_ROOT=temp_dir)
            client = app.test_client()
            payload = {
                "action": "generate_model",
                "latex": r"m_cart\ddot{x_cart}+c_damper\dot{x_cart}+k_spring x_cart=F_drive",
                "symbol_role__x_cart": "state",
                "symbol_role__m_cart": "parameter",
                "symbol_role__c_damper": "parameter",
                "symbol_role__k_spring": "parameter",
                "symbol_role__F_drive": "input",
                "symbol_value__m_cart": "2.0",
                "symbol_value__c_damper": "0.4",
                "symbol_value__k_spring": "8.0",
                "symbol_value__F_drive": "1.5",
                "symbol_input_kind__F_drive": "inport",
                "state_ic__x_cart": "1.0",
                "state_ic__x_cart_dot": "0.0",
            }

            first_response = client.post("/", data=payload)
            second_response = client.post("/", data=payload)

            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 200)
            created = sorted(output_dir.glob("run_*"))
            self.assertEqual(len(created), 2)
            self.assertNotEqual(created[0].name, created[1].name)
            self.assertTrue(all(any(path.glob("*.slx")) for path in created))

    def test_download_route_returns_generated_slx(self) -> None:
        app = create_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_deadbeefcafe"
            run_dir.mkdir(parents=True, exist_ok=True)
            model_path = run_dir / "example_model.slx"
            model_path.write_bytes(b"fake slx")
            app.config.update(TESTING=True, GUI_REPORT_ROOT=temp_dir)
            client = app.test_client()

            response = client.get("/download/run_deadbeefcafe")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"fake slx")
            self.assertIn("filename=example_model.slx", response.headers["Content-Disposition"])
            response.close()

    def test_download_route_resolves_relative_report_root_against_cwd(self) -> None:
        app = create_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_cwd = Path.cwd()
            try:
                os.chdir(temp_dir)
                relative_gui_runs = GUI_RUNS_ROOT.relative_to(Path(__file__).resolve().parents[2])
                run_dir = Path(relative_gui_runs) / "run_deadbeefcafe"
                run_dir.mkdir(parents=True, exist_ok=True)
                model_path = run_dir / "example_model.slx"
                model_path.write_bytes(b"fake slx")
                app.config.update(TESTING=True, GUI_REPORT_ROOT=str(relative_gui_runs))
                client = app.test_client()

                response = client.get("/download/run_deadbeefcafe")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, b"fake slx")
                self.assertIn("filename=example_model.slx", response.headers["Content-Disposition"])
                response.close()
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
