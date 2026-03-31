from __future__ import annotations

import unittest

import numpy as np
import pytest

from canonicalize.first_order import build_first_order_system
from canonicalize.state_space import build_state_space_system
from backend.graph_to_simulink import graph_to_simulink_model
from backend.simulate_simulink import simulation_model_params, simulate_simulink_model
from backend.validate_simulink import compare_simulink_results
from ir.graph_lowering import lower_first_order_system_graph
from latex_frontend.translator import translate_latex
from repo_paths import GENERATED_MODELS_ROOT, REPO_ROOT
from simulate.input_specs import build_input_function, normalize_input_specs
from simulate.ode_sim import constant_inputs, simulate_ode_system
from simulate.state_space_sim import simulate_state_space_system
from simulink.engine import start_engine

pytestmark = [pytest.mark.matlab, pytest.mark.slow]


class BackendIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.eng = start_engine(retries=1, retry_delay_seconds=1.0)
        cls.output_dir = GENERATED_MODELS_ROOT / "backend_tests"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.eng.quit()

    def test_mass_spring_builds_and_matches_python(self) -> None:
        equations = translate_latex(r"m\ddot{x}+c\dot{x}+kx=u")
        first_order = build_first_order_system(equations)
        state_space = build_state_space_system(first_order)
        graph = lower_first_order_system_graph(first_order, name="mass_spring_backend_test")
        params = {"m": 1.0, "c": 0.4, "k": 2.0}
        inputs = {"u": 1.0}
        initial_conditions = {"x": 0.0, "x_dot": 0.0}
        t_eval = np.linspace(0.0, 10.0, 300)
        model = graph_to_simulink_model(
            graph,
            name="mass_spring_backend_test",
            state_names=first_order["states"],
            parameter_values=params,
            input_values=inputs,
            model_params=simulation_model_params(t_span=(0.0, 10.0), t_eval=t_eval),
        )
        simulink_result = simulate_simulink_model(self.eng, model, output_dir=self.output_dir)
        ode_result = simulate_ode_system(
            first_order,
            parameter_values=params,
            initial_conditions=initial_conditions,
            input_function=constant_inputs(inputs),
            t_eval=t_eval,
        )
        state_space_result = simulate_state_space_system(
            state_space,
            parameter_values=params,
            initial_conditions=initial_conditions,
            input_function=constant_inputs(inputs),
            t_eval=t_eval,
        )
        validation = compare_simulink_results(
            simulink_result,
            ode_result,
            state_space_result,
            tolerance=1e-6,
        )
        self.assertTrue(validation["passes"])

    def test_nonlinear_pendulum_builds_and_matches_ode(self) -> None:
        equations = translate_latex(r"\ddot{\theta}+\frac{g}{l}\sin(\theta)=0")
        first_order = build_first_order_system(equations)
        graph = lower_first_order_system_graph(first_order, name="nonlinear_pendulum_backend_test")
        params = {"g": 9.81, "l": 1.0}
        initial_conditions = {"theta": 0.3, "theta_dot": 0.0}
        t_eval = np.linspace(0.0, 4.0, 320)
        model = graph_to_simulink_model(
            graph,
            name="nonlinear_pendulum_backend_test",
            state_names=first_order["states"],
            parameter_values=params,
            initial_conditions=initial_conditions,
            model_params=simulation_model_params(t_span=(0.0, 4.0), t_eval=t_eval),
        )
        simulink_result = simulate_simulink_model(self.eng, model, output_dir=self.output_dir)
        ode_result = simulate_ode_system(
            first_order,
            parameter_values=params,
            initial_conditions=initial_conditions,
            input_function=constant_inputs({}),
            t_eval=t_eval,
        )
        validation = compare_simulink_results(
            simulink_result,
            ode_result,
            None,
            tolerance=1e-6,
        )
        self.assertIsNone(validation["vs_state_space"])
        self.assertTrue(validation["passes"])

    def test_matlabv1_generate_symbolic_builds_with_workspace_inference(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqn x u m c k", nargout=0)
        self.eng.eval("info = matlabv1_setup();", nargout=0)
        self.eng.eval("syms x(t) m c k u(t)", nargout=0)
        self.eng.eval("eqn = m*diff(x,t,2) + c*diff(x,t) + k*x == u(t);", nargout=0)
        self.eng.eval("m = 5; c = 10; k = 20; u(t) = heaviside(t);", nargout=0)
        self.eng.eval(
            "out = matlabv1.generate(eqn, 'State', 'x', 'ModelName', 'matlabv1_symbolic_integration', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        source_type = self.eng.eval("out.SourceType", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        generated_model_path = self.eng.eval("out.GeneratedModelPath", nargout=1)
        block_type = self.eng.eval("get_param([out.ModelName '/u'], 'BlockType')", nargout=1)
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(source_type, "matlab_symbolic")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(generated_model_path.endswith(".slx"))
        self.assertEqual(block_type, "Step")

    def test_matlabv1_analyze_infers_equation_text_source_type(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear report", nargout=0)
        self.eng.eval("info = matlabv1_setup();", nargout=0)
        self.eng.eval(
            "report = matlabv1.analyze('xdot = -x + u', 'State', 'x', 'Inputs', {'u'});",
            nargout=0,
        )

        source_type = self.eng.eval("report.SourceType", nargout=1)
        route = self.eng.eval("report.Route", nargout=1)
        states = tuple(self.eng.eval("report.PublicOptions.States", nargout=1))

        self.assertEqual(source_type, "matlab_equation_text")
        self.assertEqual(route, "explicit_ode")
        self.assertEqual(states, ("x",))

    def test_matlabv2native_compare_with_python_reports_route_and_first_order_parity_for_mass_spring(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear cmp eqn x u m c k", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) m c k u(t)", nargout=0)
        self.eng.eval("eqn = m*diff(x,t,2) + c*diff(x,t) + k*x == u(t);", nargout=0)
        self.eng.eval("m = 5; c = 10; k = 20; u(t) = heaviside(t);", nargout=0)
        self.eng.eval("cmp = matlabv2native.compareWithPython(eqn, 'State', 'x');", nargout=0)

        backend_kind = self.eng.eval("cmp.BackendKind", nargout=1)
        source_type = self.eng.eval("cmp.SourceType", nargout=1)
        route = self.eng.eval("cmp.PythonRoute", nargout=1)
        parity_passes = self.eng.eval("cmp.ParityReport.AllComparedFieldsMatch", nargout=1)
        route_match = self.eng.eval("cmp.ParityReport.Matches.route", nargout=1)
        first_order_state_match = self.eng.eval("cmp.ParityReport.Matches.first_order_states", nargout=1)
        first_order_equation_state_match = self.eng.eval("cmp.ParityReport.Matches.first_order_equation_state_order", nargout=1)
        native_parameters = tuple(self.eng.eval("cmp.NativePreview.Parameters", nargout=1))
        python_parameters = tuple(self.eng.eval("cmp.PythonNormalizedProblem.parameters", nargout=1))
        native_first_order_states = tuple(self.eng.eval("cmp.NativePreview.FirstOrderPreview.States", nargout=1))
        python_first_order_states = tuple(self.eng.eval("cmp.PythonFirstOrder.states", nargout=1))

        self.assertEqual(backend_kind, "python_delegate")
        self.assertEqual(source_type, "matlab_symbolic")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(parity_passes)
        self.assertTrue(route_match)
        self.assertTrue(first_order_state_match)
        self.assertTrue(first_order_equation_state_match)
        self.assertEqual(native_parameters, python_parameters)
        self.assertEqual(native_first_order_states, ("x", "x_dot"))
        self.assertEqual(native_first_order_states, python_first_order_states)

    def test_matlabv2native_compare_with_python_reports_route_and_first_order_parity_for_first_order_symbolic_ode(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear cmp eqn x u", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) u(t)", nargout=0)
        self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
        self.eng.eval("u(t) = heaviside(t);", nargout=0)
        self.eng.eval("cmp = matlabv2native.compareWithPython(eqn, 'State', 'x');", nargout=0)

        route = self.eng.eval("cmp.PythonRoute", nargout=1)
        parity_passes = self.eng.eval("cmp.ParityReport.AllComparedFieldsMatch", nargout=1)
        route_match = self.eng.eval("cmp.ParityReport.Matches.route", nargout=1)
        first_order_state_match = self.eng.eval("cmp.ParityReport.Matches.first_order_states", nargout=1)
        native_first_order_states = tuple(self.eng.eval("cmp.NativePreview.FirstOrderPreview.States", nargout=1))
        python_first_order_states = tuple(self.eng.eval("cmp.PythonFirstOrder.states", nargout=1))

        self.assertEqual(route, "explicit_ode")
        self.assertTrue(parity_passes)
        self.assertTrue(route_match)
        self.assertTrue(first_order_state_match)
        self.assertEqual(native_first_order_states, ("x",))
        self.assertEqual(native_first_order_states, python_first_order_states)

    def test_matlabv2native_generate_builds_and_returns_parity_report(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqn x u m c k", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) m c k u(t)", nargout=0)
        self.eng.eval("eqn = m*diff(x,t,2) + c*diff(x,t) + k*x == u(t);", nargout=0)
        self.eng.eval("m = 5; c = 10; k = 20; u(t) = heaviside(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqn, 'State', 'x', 'ParityMode', 'python', 'ModelName', 'matlabv2native_symbolic_integration', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        generated_model_path = self.eng.eval("out.GeneratedModelPath", nargout=1)
        parity_passes = self.eng.eval("out.ParityReport.AllComparedFieldsMatch", nargout=1)
        route_match = self.eng.eval("out.ParityReport.Matches.route", nargout=1)
        first_order_state_match = self.eng.eval("out.ParityReport.Matches.first_order_states", nargout=1)
        source_family_match = self.eng.eval("out.ParityReport.Matches.source_block_family", nargout=1)
        simulation_trace_match = self.eng.eval("out.ParityReport.Matches.simulation_traces", nargout=1)
        native_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.native_vs_matlab_reference", nargout=1)
        python_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.python_vs_matlab_reference", nargout=1)
        native_vs_python_match = self.eng.eval("out.ParityReport.Matches.native_vs_python_delegate", nargout=1)
        validation_status_match = self.eng.eval("out.ParityReport.Matches.validation_status", nargout=1)
        reference_kind = self.eng.eval("out.Validation.reference_kind", nargout=1)
        native_vs_matlab_passes = self.eng.eval("out.Validation.native_vs_matlab_reference.passes", nargout=1)
        python_vs_matlab_passes = self.eng.eval("out.Validation.python_vs_matlab_reference.passes", nargout=1)
        native_vs_python_passes = self.eng.eval("out.Validation.native_vs_python_delegate.passes", nargout=1)
        block_type = self.eng.eval("get_param([out.ModelName '/u'], 'BlockType')", nargout=1)
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_with_python_parity")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(generated_model_path.endswith(".slx"))
        self.assertTrue(parity_passes)
        self.assertTrue(route_match)
        self.assertTrue(first_order_state_match)
        self.assertTrue(source_family_match)
        self.assertTrue(simulation_trace_match)
        self.assertTrue(native_vs_matlab_match)
        self.assertTrue(python_vs_matlab_match)
        self.assertTrue(native_vs_python_match)
        self.assertTrue(validation_status_match)
        self.assertEqual(reference_kind, "matlab_ode")
        self.assertTrue(native_vs_matlab_passes)
        self.assertTrue(python_vs_matlab_passes)
        self.assertTrue(native_vs_python_passes)
        self.assertEqual(block_type, "Step")

    def test_matlabv2native_generate_builds_native_first_order_anchor_model(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqn x u", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) u(t)", nargout=0)
        self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
        self.eng.eval("u(t) = heaviside(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_first_order_native', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        parity_kind = self.eng.eval("out.ParityReport.Kind", nargout=1)
        block_type = self.eng.eval("get_param([out.ModelName '/u'], 'BlockType')", nargout=1)
        native_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.native_vs_matlab_reference", nargout=1)
        validation_status_match = self.eng.eval("out.ParityReport.Matches.validation_status", nargout=1)
        reference_kind = self.eng.eval("out.Validation.reference_kind", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        native_build_sec = self.eng.eval("out.Timing.native_build_sec", nargout=1)
        native_simulation_sec = self.eng.eval("out.Timing.native_simulation_sec", nargout=1)
        matlab_reference_sec = self.eng.eval("out.Timing.matlab_reference_sec", nargout=1)
        python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
        total_wall_time_sec = self.eng.eval("out.Timing.total_wall_time_sec", nargout=1)
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertEqual(parity_kind, "runtime_phase5_native_only")
        self.assertEqual(block_type, "Step")
        self.assertTrue(native_vs_matlab_match)
        self.assertTrue(validation_status_match)
        self.assertEqual(reference_kind, "matlab_ode")
        self.assertTrue(validation_passes)
        self.assertGreater(native_build_sec, 0.0)
        self.assertGreater(native_simulation_sec, 0.0)
        self.assertGreater(matlab_reference_sec, 0.0)
        self.assertEqual(python_parity_sec, 0.0)
        self.assertGreater(total_wall_time_sec, 0.0)

    def test_matlabv2native_generate_uses_matlab_function_source_for_unsupported_input_expression(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqn x u", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) u(t)", nargout=0)
        self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
        self.eng.eval("u(t) = erf(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_fallback_native', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        block_type = self.eng.eval("get_param([out.ModelName '/u'], 'BlockType')", nargout=1)
        sf_block_type = self.eng.eval("get_param([out.ModelName '/u'], 'SFBlockType')", nargout=1)
        has_source_family_match = self.eng.eval("isfield(out.ParityReport.Matches, 'source_block_family')", nargout=1)
        native_vs_matlab_passes = self.eng.eval("out.Validation.native_vs_matlab_reference.passes", nargout=1)
        has_python_vs_matlab = self.eng.eval("isfield(out.Validation, 'python_vs_matlab_reference')", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(block_type, "SubSystem")
        self.assertEqual(sf_block_type, "MATLAB Function")
        self.assertFalse(has_source_family_match)
        self.assertTrue(native_vs_matlab_passes)
        self.assertFalse(has_python_vs_matlab)
        self.assertTrue(validation_passes)

    def test_matlabv2native_generate_builds_native_coupled_explicit_system(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns x y u", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) y(t) u(t)", nargout=0)
        self.eng.eval("eqns = [diff(x,t) == -x + y + u(t); diff(y,t) == -2*y + x];", nargout=0)
        self.eng.eval("u(t) = heaviside(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x','y'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_coupled_native', 'OpenModel', false);",
            nargout=0,
        )

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))
        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x", "y"))

    def test_matlabv2native_generate_builds_coupled_explicit_system_with_python_parity(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns x y u", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) y(t) u(t)", nargout=0)
        self.eng.eval("eqns = [diff(x,t) == -x + y + u(t); diff(y,t) == -2*y + x];", nargout=0)
        self.eng.eval("u(t) = heaviside(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x','y'}, 'ParityMode', 'python', 'ModelName', 'matlabv2native_coupled_parity', 'OpenModel', false);",
            nargout=0,
        )

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route_match = self.eng.eval("out.ParityReport.Matches.route", nargout=1)
        first_order_state_match = self.eng.eval("out.ParityReport.Matches.first_order_states", nargout=1)
        source_family_match = self.eng.eval("out.ParityReport.Matches.source_block_family", nargout=1)
        native_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.native_vs_matlab_reference", nargout=1)
        python_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.python_vs_matlab_reference", nargout=1)
        native_vs_python_match = self.eng.eval("out.ParityReport.Matches.native_vs_python_delegate", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)

        self.assertEqual(backend_kind, "native_with_python_parity")
        self.assertTrue(route_match)
        self.assertTrue(first_order_state_match)
        self.assertTrue(source_family_match)
        self.assertTrue(native_vs_matlab_match)
        self.assertTrue(python_vs_matlab_match)
        self.assertTrue(native_vs_python_match)
        self.assertTrue(validation_passes)

    def test_matlabv2native_runtime_native_supports_pulse_ramp_and_sine_specs(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "pulse",
                "u = struct('kind','pulse','amplitude',2,'start_time',0.3,'width',0.2);",
                "PulseGenerator",
            ),
            (
                "ramp",
                "u = struct('kind','ramp','slope',2,'start_time',0.5,'initial_output',-1);",
                "Ramp",
            ),
            (
                "sine",
                "u = struct('kind','sine','amplitude',2,'frequency',1.5,'phase',0.25,'bias',1);",
                "SineWave",
            ),
        ]

        for case_name, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval("syms x(t) u", nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u;", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_{case_name}_native', 'OpenModel', false);",
                    nargout=0,
                )

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                self.assertEqual(backend_kind, "native_runtime_only")
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertEqual(python_parity_sec, 0.0)

    def test_matlabv2native_runtime_native_supports_square_specs(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "square",
                "u = struct('kind','square','amplitude',1,'frequency',3,'phase',0,'bias',0);",
                "SquareWave",
            ),
        ]

        for case_name, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval("syms x(t) u", nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u;", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_{case_name}_runtime', 'OpenModel', false);",
                    nargout=0,
                )
                self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                rhs_block_type = self.eng.eval("get_param([out.ModelName '/rhs_x'], 'BlockType')", nargout=1)
                has_rhs_matlab_function = self.eng.eval(
                    "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/rhs_x']))",
                    nargout=1,
                )
                self.eng.eval("bdclose(out.ModelName);", nargout=0)
                self.assertEqual(backend_kind, "native_runtime_only")
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertEqual(python_parity_sec, 0.0)
                self.assertEqual(rhs_block_type, "Sum")
                self.assertFalse(has_rhs_matlab_function)

    def test_matlabv2native_python_parity_mode_supports_square_specs(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "square",
                "u = struct('kind','square','amplitude',1,'frequency',3,'phase',0,'bias',0);",
                "SquareWave",
            ),
        ]

        for case_name, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval("syms x(t) u", nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u;", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'ParityMode', 'python', 'ModelName', 'matlabv2native_{case_name}_runtime_parity', 'OpenModel', false);",
                    nargout=0,
                )

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                source_family_match = self.eng.eval("out.ParityReport.Matches.source_block_family", nargout=1)
                native_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.native_vs_matlab_reference", nargout=1)
                python_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.python_vs_matlab_reference", nargout=1)
                native_vs_python_match = self.eng.eval("out.ParityReport.Matches.native_vs_python_delegate", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                self.assertEqual(backend_kind, "native_with_python_parity")
                self.assertTrue(source_family_match)
                self.assertTrue(native_vs_matlab_match)
                self.assertTrue(python_vs_matlab_match)
                self.assertTrue(native_vs_python_match)
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertGreater(python_parity_sec, 0.0)

    def test_matlabv2native_python_parity_mode_supports_pulse_ramp_and_sine_specs(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "pulse",
                "u = struct('kind','pulse','amplitude',2,'start_time',0.3,'width',0.2);",
                "PulseGenerator",
            ),
            (
                "ramp",
                "u = struct('kind','ramp','slope',2,'start_time',0.5,'initial_output',-1);",
                "Ramp",
            ),
            (
                "sine",
                "u = struct('kind','sine','amplitude',2,'frequency',1.5,'phase',0.25,'bias',1);",
                "SineWave",
            ),
        ]

        for case_name, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval("syms x(t) u", nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u;", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'ParityMode', 'python', 'ModelName', 'matlabv2native_{case_name}_parity', 'OpenModel', false);",
                    nargout=0,
                )

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                source_family_match = self.eng.eval("out.ParityReport.Matches.source_block_family", nargout=1)
                native_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.native_vs_matlab_reference", nargout=1)
                python_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.python_vs_matlab_reference", nargout=1)
                native_vs_python_match = self.eng.eval("out.ParityReport.Matches.native_vs_python_delegate", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                self.assertEqual(backend_kind, "native_with_python_parity")
                self.assertTrue(source_family_match)
                self.assertTrue(native_vs_matlab_match)
                self.assertTrue(python_vs_matlab_match)
                self.assertTrue(native_vs_python_match)
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertGreater(python_parity_sec, 0.0)

    def test_matlabv2native_runtime_native_supports_sawtooth_and_triangle_expression_specs(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "sawtooth",
                "u = struct('kind','expression','expression','1.1*sawtooth(4*t)','time_variable','t');",
                "RepeatingSequence",
            ),
            (
                "triangle",
                "u = struct('kind','expression','expression','0.8*sawtooth(3*t, 0.5)','time_variable','t');",
                "RepeatingSequence",
            ),
        ]

        for case_name, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval("syms x(t) u", nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u;", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_{case_name}_expression_spec_runtime', 'OpenModel', false);",
                    nargout=0,
                )

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                self.assertEqual(backend_kind, "native_runtime_only")
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertEqual(python_parity_sec, 0.0)

    def test_matlabv2native_symbolic_sawtooth_and_triangle_are_expression_spec_only(self) -> None:
        cases = [
            ("sawtooth", "tmp = sawtooth(4*t);"),
            ("triangle", "tmp = sawtooth(3*t, 0.5);"),
        ]

        for case_name, raw_expression in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear raw_supported raw_message t tmp", nargout=0)
                self.eng.eval("syms t real", nargout=0)
                self.eng.eval("raw_supported = true; raw_message = \"\";", nargout=0)
                self.eng.eval(
                    f"try, {raw_expression}; catch exc, raw_supported = false; raw_message = string(exc.message); end;",
                    nargout=0,
                )

                raw_supported = self.eng.eval("raw_supported", nargout=1)
                raw_message = self.eng.eval("char(raw_message)", nargout=1)

                self.assertFalse(raw_supported)
                self.assertIn("single, double", raw_message)

    def test_matlabv2native_runtime_native_supports_symbolic_waveform_expressions(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "pulse_symbolic",
                "syms x(t) u(t)",
                "u(t) = 2*heaviside(t-1) - 2*heaviside(t-3/2);",
                "PulseGenerator",
            ),
            (
                "ramp_symbolic",
                "syms x(t) u(t)",
                "u(t) = heaviside(t - 1) * (2*t - 2) + 3;",
                "Ramp",
            ),
            (
                "sine_symbolic",
                "syms x(t) u(t)",
                "u(t) = 1.5*sin(2*t + 0.1) - 0.2;",
                "SineWave",
            ),
            (
                "square_symbolic",
                "syms x(t) u(t)",
                "u(t) = 1.2*sign(sin(3*t + 0.2)) - 0.1;",
                "SquareWave",
            ),
        ]

        for case_name, symbolic_setup, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval(symbolic_setup, nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_{case_name}_runtime', 'OpenModel', false);",
                    nargout=0,
                )

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                self.assertEqual(backend_kind, "native_runtime_only")
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertEqual(python_parity_sec, 0.0)

    def test_matlabv2native_python_parity_mode_supports_symbolic_waveform_expressions(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "pulse_symbolic",
                "syms x(t) u(t)",
                "u(t) = 2*heaviside(t-1) - 2*heaviside(t-3/2);",
                "PulseGenerator",
            ),
            (
                "ramp_symbolic",
                "syms x(t) u(t)",
                "u(t) = heaviside(t - 1) * (2*t - 2) + 3;",
                "Ramp",
            ),
            (
                "sine_symbolic",
                "syms x(t) u(t)",
                "u(t) = 1.5*sin(2*t + 0.1) - 0.2;",
                "SineWave",
            ),
            (
                "square_symbolic",
                "syms x(t) u(t)",
                "u(t) = 1.2*sign(sin(3*t + 0.2)) - 0.1;",
                "SquareWave",
            ),
        ]

        for case_name, symbolic_setup, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval(symbolic_setup, nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'ParityMode', 'python', 'ModelName', 'matlabv2native_{case_name}_parity', 'OpenModel', false);",
                    nargout=0,
                )

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                source_family_match = self.eng.eval("out.ParityReport.Matches.source_block_family", nargout=1)
                native_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.native_vs_matlab_reference", nargout=1)
                python_vs_matlab_match = self.eng.eval("out.ParityReport.Matches.python_vs_matlab_reference", nargout=1)
                native_vs_python_match = self.eng.eval("out.ParityReport.Matches.native_vs_python_delegate", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                self.assertEqual(backend_kind, "native_with_python_parity")
                self.assertTrue(source_family_match)
                self.assertTrue(native_vs_matlab_match)
                self.assertTrue(python_vs_matlab_match)
                self.assertTrue(native_vs_python_match)
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertGreater(python_parity_sec, 0.0)

    def test_matlabv2native_runtime_native_supports_symbolic_nonlinear_expressions(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "saturation_symbolic",
                "syms x(t) u(t)",
                "u(t) = min(max(2*sin(t), -0.5), 0.75);",
                "Saturation",
            ),
            (
                "dead_zone_symbolic",
                "syms x(t) u(t)",
                "u(t) = piecewise(abs(t) < 1/2, 0, 1/2 < t, t - 1/2, t + 1/2);",
                "DeadZone",
            ),
            (
                "sign_symbolic",
                "syms x(t) u(t)",
                "u(t) = sign(t);",
                "Sign",
            ),
            (
                "abs_symbolic",
                "syms x(t) u(t)",
                "u(t) = abs(t);",
                "Abs",
            ),
            (
                "max_symbolic",
                "syms x(t) u(t)",
                "u(t) = max(sin(t), 0.2);",
                "MinMax",
            ),
            (
                "min_symbolic",
                "syms x(t) u(t)",
                "u(t) = min(sin(t), 0.2);",
                "MinMax",
            ),
        ]

        for case_name, symbolic_setup, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval(symbolic_setup, nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_{case_name}_runtime', 'OpenModel', false);",
                    nargout=0,
                )
                self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                source_block_type = self.eng.eval("get_param([out.ModelName '/u'], 'BlockType')", nargout=1)
                has_source_matlab_function = self.eng.eval(
                    "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/u']))",
                    nargout=1,
                )
                self.eng.eval("bdclose(out.ModelName);", nargout=0)
                self.assertEqual(backend_kind, "native_runtime_only")
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertEqual(python_parity_sec, 0.0)
                self.assertNotEqual(source_block_type, "SubSystem")
                self.assertFalse(has_source_matlab_function)

    def test_matlabv2native_runtime_native_supports_symbolic_math_expressions(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)

        cases = [
            (
                "atan_symbolic",
                "syms x(t) u(t)",
                "u(t) = atan(t);",
                "TrigonometricFunction",
            ),
            (
                "atan2_symbolic",
                "syms x(t) u(t)",
                "u(t) = atan2(t, t + 1);",
                "TrigonometricFunction",
            ),
            (
                "exp_symbolic",
                "syms x(t) u(t)",
                "u(t) = exp(-0.5*t);",
                "MathFunction",
            ),
            (
                "log_symbolic",
                "syms x(t) u(t)",
                "u(t) = log(t + 2);",
                "MathFunction",
            ),
            (
                "sqrt_symbolic",
                "syms x(t) u(t)",
                "u(t) = sqrt(t + 1);",
                "MathFunction",
            ),
        ]

        for case_name, symbolic_setup, input_setup, expected_family in cases:
            with self.subTest(case=case_name):
                self.eng.eval("clear out eqn x u t", nargout=0)
                self.eng.eval(symbolic_setup, nargout=0)
                self.eng.eval("eqn = diff(x,t) == -x + u(t);", nargout=0)
                self.eng.eval(input_setup, nargout=0)
                self.eng.eval(
                    f"out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_{case_name}_runtime', 'OpenModel', false);",
                    nargout=0,
                )
                self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

                backend_kind = self.eng.eval("out.BackendKind", nargout=1)
                validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
                source_family = self.eng.eval("out.SourceBlockFamilies.u", nargout=1)
                python_parity_sec = self.eng.eval("out.Timing.python_parity_sec", nargout=1)
                source_block_type = self.eng.eval("get_param([out.ModelName '/u'], 'BlockType')", nargout=1)
                has_source_matlab_function = self.eng.eval(
                    "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/u']))",
                    nargout=1,
                )
                self.eng.eval("bdclose(out.ModelName);", nargout=0)

                self.assertEqual(backend_kind, "native_runtime_only")
                self.assertTrue(validation_passes)
                self.assertEqual(source_family, expected_family)
                self.assertEqual(python_parity_sec, 0.0)
                self.assertNotEqual(source_block_type, "SubSystem")
                self.assertFalse(has_source_matlab_function)

    def test_matlabv2native_generate_builds_native_cart_pendulum_benchmark(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns x theta m_1 m_2 l I g k", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) theta(t) m_1 m_2 l I g k", nargout=0)
        self.eng.eval(
            "eqns = [(m_1 + m_2)*diff(x,t,2) + (m_2*l/2)*cos(theta)*diff(theta,t,2) - (m_2*l/2)*sin(theta)*diff(theta,t)^2 + k*x == 0; (m_2*l/2)*cos(theta)*diff(x,t,2) + (1/4)*(m_2*l^2 + 4*I)*diff(theta,t,2) + (m_2*g*l/2)*sin(theta) == 0];",
            nargout=0,
        )
        self.eng.eval("m_1 = 10; m_2 = 2; l = 1; I = 0.17; g = 9.81; k = 100;", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x','theta'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_cart_pendulum_benchmark', 'OpenModel', false);",
            nargout=0,
        )

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x", "x_dot", "theta", "theta_dot"))

    def test_matlabv2native_generate_builds_native_planar_quadrotor_benchmark(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns x z theta u1 u2 m I L g", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) z(t) theta(t) u1(t) u2(t) m I L g", nargout=0)
        self.eng.eval(
            "eqns = [m*diff(x,t,2) == -(u1(t)+u2(t))*sin(theta); m*diff(z,t,2) == (u1(t)+u2(t))*cos(theta) - m*g; I*diff(theta,t,2) == L*(u1(t)-u2(t))];",
            nargout=0,
        )
        self.eng.eval("m = 1.2; I = 0.03; L = 0.25; g = 9.81;", nargout=0)
        self.eng.eval("u1(t) = 1 + heaviside(t);", nargout=0)
        self.eng.eval("u2(t) = 1;", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x','z','theta'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_planar_quadrotor_benchmark', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        source_family_u1 = self.eng.eval("out.SourceBlockFamilies.u1", nargout=1)
        source_family_u2 = self.eng.eval("out.SourceBlockFamilies.u2", nargout=1)
        source_block_u1 = self.eng.eval("get_param([out.ModelName '/u1'], 'BlockType')", nargout=1)
        has_source_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/u1']))",
            nargout=1,
        )
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(source_family_u1, "Step")
        self.assertEqual(source_family_u2, "Constant")
        self.assertEqual(source_block_u1, "Step")
        self.assertFalse(has_source_matlab_function)

    def test_matlabv2native_generate_builds_native_acrobot_benchmark(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns theta1 theta2 omega1 omega2 tau m1 m2 l1 lc1 lc2 I1 I2 g d1 d2 phi1 phi2 denom", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms theta1(t) theta2(t) omega1(t) omega2(t) tau(t) m1 m2 l1 lc1 lc2 I1 I2 g d1 d2 phi1 phi2 denom", nargout=0)
        self.eng.eval("d1 = m1*lc1^2 + m2*(l1^2 + lc2^2 + 2*l1*lc2*cos(theta2)) + I1 + I2;", nargout=0)
        self.eng.eval("d2 = m2*(lc2^2 + l1*lc2*cos(theta2)) + I2;", nargout=0)
        self.eng.eval("phi2 = m2*lc2*g*cos(theta1 + theta2 - pi/2);", nargout=0)
        self.eng.eval("phi1 = -m2*l1*lc2*omega2^2*sin(theta2) - 2*m2*l1*lc2*omega2*omega1*sin(theta2) + (m1*lc1 + m2*l1)*g*cos(theta1 - pi/2) + phi2;", nargout=0)
        self.eng.eval("denom = m2*lc2^2 + I2 - d2^2/d1;", nargout=0)
        self.eng.eval(
            "eqns = [diff(theta1,t) == omega1; diff(theta2,t) == omega2; diff(omega1,t) == -(d2*((tau(t) + d2/d1*phi1 - m2*l1*lc2*omega1^2*sin(theta2) - phi2)/denom) + phi1)/d1; diff(omega2,t) == (tau(t) + d2/d1*phi1 - m2*l1*lc2*omega1^2*sin(theta2) - phi2)/denom];",
            nargout=0,
        )
        self.eng.eval("m1 = 1.0; m2 = 1.0; l1 = 1.0; lc1 = 0.5; lc2 = 0.5; I1 = 0.2; I2 = 0.2; g = 9.81;", nargout=0)
        self.eng.eval("tau(t) = 0.1 + 0.2*heaviside(t - 0.5);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'theta1','theta2','omega1','omega2'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_acrobot_benchmark', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        source_family_tau = self.eng.eval("out.SourceBlockFamilies.tau", nargout=1)
        source_block_tau = self.eng.eval("get_param([out.ModelName '/tau'], 'BlockType')", nargout=1)
        has_source_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/tau']))",
            nargout=1,
        )
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(source_family_tau, "Step")
        self.assertEqual(source_block_tau, "Step")
        self.assertFalse(has_source_matlab_function)
        self.assertEqual(first_order_states, ("theta1", "theta2", "omega1", "omega2"))

    def test_matlabv2native_generate_builds_native_reducible_dae_benchmark(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns x z", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t) z(t)", nargout=0)
        self.eng.eval("eqns = [diff(x,t) == z; 0 == z - sin(t)];", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x'}, 'Algebraics', {'z'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_reducible_dae_benchmark', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        preview_route = self.eng.eval("out.NativePreview.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))
        first_rhs = self.eng.eval("char(out.NativePreview.FirstOrderPreview.StateEquations(1).rhs)", nargout=1)
        rhs_block_type = self.eng.eval("get_param([out.ModelName '/rhs_x'], 'BlockType')", nargout=1)
        has_rhs_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/rhs_x']))",
            nargout=1,
        )
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "dae_reduced_to_explicit_ode")
        self.assertEqual(preview_route, "dae_reduced_to_explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x",))
        self.assertEqual(first_rhs, "sin(t)")
        self.assertIn(rhs_block_type, ("Sin", "SineWave"))
        self.assertFalse(has_rhs_matlab_function)

    def test_matlabv2native_generate_builds_native_affine_time_rhs_without_matlab_function(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqn x", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x(t)", nargout=0)
        self.eng.eval("eqn = diff(x,t) == t + 1;", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqn, 'State', 'x', 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_affine_time_rhs_native', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        rhs_block_type = self.eng.eval("get_param([out.ModelName '/rhs_x'], 'BlockType')", nargout=1)
        has_rhs_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/rhs_x']))",
            nargout=1,
        )
        has_clock = self.eng.eval("bdIsLoaded(out.ModelName) && ~isempty(find_system(out.ModelName, 'SearchDepth', 1, 'BlockType', 'Clock'))", nargout=1)
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(rhs_block_type, "Sum")
        self.assertTrue(has_clock)
        self.assertFalse(has_rhs_matlab_function)

    def test_matlabv2native_generate_builds_native_vector_form_linear_system(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns X A x1 x2 x3", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x1(t) x2(t) x3(t)", nargout=0)
        self.eng.eval("X = [x1; x2; x3];", nargout=0)
        self.eng.eval("A = sym([0 1 0; 0 0 1; -1 -2 -3]);", nargout=0)
        self.eng.eval("eqns = diff(X,t) == A*X;", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x1','x2','x3'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_vector_linear_native', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))
        rhs_block_type = self.eng.eval("get_param([out.ModelName '/rhs_x3'], 'BlockType')", nargout=1)
        has_rhs_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/rhs_x3']))",
            nargout=1,
        )
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x1", "x2", "x3"))
        self.assertEqual(rhs_block_type, "Sum")
        self.assertFalse(has_rhs_matlab_function)

    def test_matlabv2native_generate_builds_native_vector_form_affine_input_system(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns X A B u x1 x2 x3", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x1(t) x2(t) x3(t) u(t)", nargout=0)
        self.eng.eval("X = [x1; x2; x3];", nargout=0)
        self.eng.eval("A = sym([0 1 0; 0 0 1; -1 -2 -3]);", nargout=0)
        self.eng.eval("B = sym([0; 0; 1]);", nargout=0)
        self.eng.eval("u(t) = 1 + heaviside(t - 0.5);", nargout=0)
        self.eng.eval("eqns = diff(X,t) == A*X + B*u(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x1','x2','x3'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_vector_affine_native', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))
        rhs_block_type = self.eng.eval("get_param([out.ModelName '/rhs_x3'], 'BlockType')", nargout=1)
        has_rhs_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/rhs_x3']))",
            nargout=1,
        )
        has_step_block = self.eng.eval(
            "bdIsLoaded(out.ModelName) && ~isempty(find_system(out.ModelName, 'SearchDepth', 1, 'BlockType', 'Step'))",
            nargout=1,
        )
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x1", "x2", "x3"))
        self.assertEqual(rhs_block_type, "Sum")
        self.assertTrue(has_step_block)
        self.assertFalse(has_rhs_matlab_function)

    def test_matlabv2native_generate_preserves_explicit_state_order_for_vector_form_system(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns X A B u x1 x2 x3", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x1(t) x2(t) x3(t) u(t)", nargout=0)
        self.eng.eval("X = [x1; x2; x3];", nargout=0)
        self.eng.eval("A = sym([0 1 0; 0 0 1; -1 -2 -3]);", nargout=0)
        self.eng.eval("B = sym([0; 0; 1]);", nargout=0)
        self.eng.eval("u(t) = 1 + heaviside(t - 0.5);", nargout=0)
        self.eng.eval("eqns = diff(X,t) == A*X + B*u(t);", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x3','x1','x2'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_vector_affine_reordered_native', 'OpenModel', false);",
            nargout=0,
        )

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x3", "x1", "x2"))

    def test_matlabv2native_generate_builds_native_vector_form_reducible_dae(self) -> None:
        repo_root = str(REPO_ROOT).replace("'", "''")
        self.eng.eval(f"cd('{repo_root}')", nargout=0)
        self.eng.eval("clear out eqns X x1 x2 z", nargout=0)
        self.eng.eval("info = matlabv2native_setup();", nargout=0)
        self.eng.eval("syms x1(t) x2(t) z(t)", nargout=0)
        self.eng.eval("X = [x1; x2];", nargout=0)
        self.eng.eval("eqns = [diff(X,t) == [z; -x1]; 0 == z - sin(t)];", nargout=0)
        self.eng.eval(
            "out = matlabv2native.generate(eqns, 'State', {'x1','x2'}, 'Algebraics', {'z'}, 'PythonExecutable', '__missing_python__', 'ModelName', 'matlabv2native_vector_reducible_dae_native', 'OpenModel', false);",
            nargout=0,
        )
        self.eng.eval("load_system(out.GeneratedModelPath);", nargout=0)

        backend_kind = self.eng.eval("out.BackendKind", nargout=1)
        route = self.eng.eval("out.Route", nargout=1)
        preview_route = self.eng.eval("out.NativePreview.Route", nargout=1)
        validation_passes = self.eng.eval("out.Validation.passes", nargout=1)
        first_order_states = tuple(self.eng.eval("out.FirstOrder.states", nargout=1))
        rhs_block_type = self.eng.eval("get_param([out.ModelName '/rhs_x1'], 'BlockType')", nargout=1)
        has_rhs_matlab_function = self.eng.eval(
            "any(strcmp(find_system(out.ModelName, 'SearchDepth', 1, 'LookUnderMasks', 'all', 'FollowLinks', 'on', 'SFBlockType', 'MATLAB Function'), [out.ModelName '/rhs_x1']))",
            nargout=1,
        )
        self.eng.eval("bdclose(out.ModelName);", nargout=0)

        self.assertEqual(backend_kind, "native_runtime_only")
        self.assertEqual(route, "dae_reduced_to_explicit_ode")
        self.assertEqual(preview_route, "dae_reduced_to_explicit_ode")
        self.assertTrue(validation_passes)
        self.assertEqual(first_order_states, ("x1", "x2"))
        self.assertIn(rhs_block_type, ("Sin", "SineWave"))
        self.assertFalse(has_rhs_matlab_function)

    def test_matlabv2native_native_preview_classifies_vector_form_irreducible_dae_as_dae_algebraic(self) -> None:
        self.eng.eval("clear preview opts caller eqns X x1 x2 z", nargout=0)
        self.eng.eval("syms x1(t) x2(t) z(t)", nargout=0)
        self.eng.eval("X = [x1; x2];", nargout=0)
        self.eng.eval("eqns = [diff(X,t) == [z; -x1]; 0 == z^2 + x1 - 1];", nargout=0)
        self.eng.eval(
            "opts = simucopilot.internal.validateOptions(struct('Build', false, 'OpenModel', false), 'States', {'x1','x2'}, 'Algebraics', {'z'}, 'TimeVariable', 't');",
            nargout=0,
        )
        self.eng.eval("caller = struct('x1', x1, 'x2', x2, 'z', z);", nargout=0)
        self.eng.eval(
            "preview = matlabv2native.internal.nativeAnalyze('matlab_symbolic', eqns, opts, caller);",
            nargout=0,
        )

        route = self.eng.eval("preview.Route", nargout=1)
        route_status = self.eng.eval("preview.RouteStatus", nargout=1)
        first_order_available = self.eng.eval("preview.FirstOrderPreview.Available", nargout=1)
        notes = tuple(self.eng.eval("cellstr(string(preview.Notes))", nargout=1))

        self.assertEqual(route, "dae_algebraic")
        self.assertEqual(route_status, "delegated")
        self.assertFalse(first_order_available)
        self.assertTrue(any("DAE/algebraic route delegated" in note for note in notes))

    def test_matlabv2native_native_preview_classifies_irreducible_dae_as_dae_algebraic(self) -> None:
        self.eng.eval("clear preview opts caller eqns x z", nargout=0)
        self.eng.eval("syms x(t) z(t)", nargout=0)
        self.eng.eval("eqns = [diff(x,t) == z; 0 == z^2 + x - 1];", nargout=0)
        self.eng.eval(
            "opts = simucopilot.internal.validateOptions(struct('Build', false, 'OpenModel', false), 'States', {'x'}, 'Algebraics', {'z'}, 'TimeVariable', 't');",
            nargout=0,
        )
        self.eng.eval("caller = struct('x', x, 'z', z);", nargout=0)
        self.eng.eval(
            "preview = matlabv2native.internal.nativeAnalyze('matlab_symbolic', eqns, opts, caller);",
            nargout=0,
        )

        route = self.eng.eval("preview.Route", nargout=1)
        route_status = self.eng.eval("preview.RouteStatus", nargout=1)
        first_order_available = self.eng.eval("preview.FirstOrderPreview.Available", nargout=1)
        notes = tuple(self.eng.eval("cellstr(string(preview.Notes))", nargout=1))

        self.assertEqual(route, "dae_algebraic")
        self.assertEqual(route_status, "delegated")
        self.assertFalse(first_order_available)
        self.assertTrue(any("DAE/algebraic route delegated" in note for note in notes))

    def _run_input_validation_case(
        self,
        *,
        case_name: str,
        raw_input_spec: dict[str, object],
        t_span: tuple[float, float],
        sample_count: int,
        tolerance: float,
        required_blocks: list[tuple[str, str | None, str | None]],
        forbidden_block_types: set[str],
    ) -> None:
        equations = translate_latex(r"\dot{x}=-x+u")
        first_order = build_first_order_system(equations)
        graph = lower_first_order_system_graph(first_order, name=f"{case_name}_backend_test")
        t_eval = np.linspace(float(t_span[0]), float(t_span[1]), sample_count)
        normalized_specs = normalize_input_specs(input_specs={"u": raw_input_spec}, t_span=t_span)
        input_function = build_input_function(input_specs=normalized_specs, t_span=t_span)

        model = graph_to_simulink_model(
            graph,
            name=f"{case_name}_backend_test",
            state_names=first_order["states"],
            input_specs=normalized_specs,
            initial_conditions={"x": 0.0},
            model_params=simulation_model_params(t_span=t_span, t_eval=t_eval),
        )
        block_specs = list(model["blocks"].values())
        block_types = {spec["type"] for spec in block_specs}
        for block_type, param_name, expected_value in required_blocks:
            self.assertTrue(
                any(
                    spec["type"] == block_type
                    and (
                        param_name is None
                        or str(spec.get("params", {}).get(param_name)) == str(expected_value)
                    )
                    for spec in block_specs
                ),
                msg=f"{case_name}: expected block {block_type} with {param_name}={expected_value}",
            )
        self.assertTrue(
            block_types.isdisjoint(forbidden_block_types),
            msg=f"{case_name}: forbidden block types present: {block_types & forbidden_block_types}",
        )

        simulink_result = simulate_simulink_model(self.eng, model, output_dir=self.output_dir)
        ode_result = simulate_ode_system(
            first_order,
            initial_conditions={"x": 0.0},
            input_function=input_function,
            t_eval=t_eval,
        )
        validation = compare_simulink_results(
            simulink_result,
            ode_result,
            None,
            tolerance=tolerance,
        )
        self.assertTrue(
            validation["passes"],
            msg=(
                f"{case_name}: validation failed with "
                f"rmse={validation['vs_ode']['rmse']} max_abs_error={validation['vs_ode']['max_abs_error']}"
            ),
        )

    def test_supported_input_validation_matrix_builds_and_matches_python(self) -> None:
        cases = [
            {
                "name": "step_native",
                "input_spec": {"kind": "expression", "expression": "2*heaviside(t - 0.5) - 0.25", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("Step", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "impulse_native",
                "input_spec": {"kind": "expression", "expression": "1.5*dirac(t - 0.5)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 5e-3,
                "required_blocks": [("PulseGenerator", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "pulse_native",
                "input_spec": {"kind": "expression", "expression": "2*heaviside(t - 0.3) - 2*heaviside(t - 0.5)", "time_variable": "t"},
                "t_span": (0.0, 1.2),
                "sample_count": 241,
                "tolerance": 1e-4,
                "required_blocks": [("PulseGenerator", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "ramp_native",
                "input_spec": {"kind": "expression", "expression": "1.2*(t - 0.25)*heaviside(t - 0.25) + 0.1", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("Ramp", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "sine_native",
                "input_spec": {"kind": "expression", "expression": "1.5*sin(2*t + 0.1) - 0.2", "time_variable": "t"},
                "t_span": (0.0, 2.0),
                "sample_count": 401,
                "tolerance": 1e-5,
                "required_blocks": [("SineWave", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "square_native",
                "input_spec": {"kind": "expression", "expression": "1.2*sign(sin(3*t - 0.2)) + 0.3", "time_variable": "t"},
                "t_span": (0.0, 2.0),
                "sample_count": 401,
                "tolerance": 1e-4,
                "required_blocks": [("SineWave", None, None), ("Sign", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "sawtooth_native",
                "input_spec": {"kind": "expression", "expression": "1.1*sawtooth(4*t)", "time_variable": "t"},
                "t_span": (0.0, 2.0),
                "sample_count": 401,
                "tolerance": 1e-4,
                "required_blocks": [("RepeatingSequence", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "triangle_native",
                "input_spec": {"kind": "expression", "expression": "0.8*sawtooth(3*t, 0.5)", "time_variable": "t"},
                "t_span": (0.0, 2.0),
                "sample_count": 401,
                "tolerance": 1e-4,
                "required_blocks": [("RepeatingSequence", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "saturation_native",
                "input_spec": {"kind": "expression", "expression": "min(max(2*sin(t), -0.5), 0.75)", "time_variable": "t"},
                "t_span": (0.0, 2.0),
                "sample_count": 401,
                "tolerance": 1e-5,
                "required_blocks": [("Saturation", None, None), ("SineWave", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "dead_zone_native",
                "input_spec": {
                    "kind": "expression",
                    "expression": "piecewise((0, abs(t) < 0.5), (t - 0.5, t > 0.5), (t + 0.5, True))",
                    "time_variable": "t",
                },
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("DeadZone", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "minmax_native",
                "input_spec": {"kind": "expression", "expression": "max(sin(t), t - 0.5)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("MinMax", "Function", "max")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "atan_native",
                "input_spec": {"kind": "expression", "expression": "atan(t)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("TrigonometricFunction", "Operator", "atan")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "atan2_native",
                "input_spec": {"kind": "expression", "expression": "atan2(t, t + 1)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("TrigonometricFunction", "Operator", "atan2")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "sec_native",
                "input_spec": {"kind": "expression", "expression": "sec(0.3*t)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("TrigonometricFunction", "Operator", "cos"), ("Divide", None, None)],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "tanh_native",
                "input_spec": {"kind": "expression", "expression": "tanh(t)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("TrigonometricFunction", "Operator", "tanh")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "log_native",
                "input_spec": {"kind": "expression", "expression": "log(t + 2)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("MathFunction", "Operator", "log")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "sqrt_native",
                "input_spec": {"kind": "expression", "expression": "sqrt(t + 1)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("MathFunction", "Operator", "sqrt")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "exp_native",
                "input_spec": {"kind": "expression", "expression": "exp(-0.5*t)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("MathFunction", "Operator", "exp")],
                "forbidden": {"FromWorkspace", "MATLABFunction"},
            },
            {
                "name": "fallback_erf",
                "input_spec": {"kind": "expression", "expression": "erf(t)", "time_variable": "t"},
                "t_span": (0.0, 1.5),
                "sample_count": 301,
                "tolerance": 1e-5,
                "required_blocks": [("MATLABFunction", None, None), ("Clock", None, None)],
                "forbidden": {"FromWorkspace"},
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                self._run_input_validation_case(
                    case_name=case["name"],
                    raw_input_spec=case["input_spec"],
                    t_span=case["t_span"],
                    sample_count=case["sample_count"],
                    tolerance=case["tolerance"],
                    required_blocks=case["required_blocks"],
                    forbidden_block_types=case["forbidden"],
                )


if __name__ == "__main__":
    unittest.main()
