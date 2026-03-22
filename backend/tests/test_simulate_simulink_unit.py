from __future__ import annotations

import importlib
import sys
import types

import pytest


class FakeSimEngine:
    def __init__(self) -> None:
        self.workspace: dict[str, object] = {}
        self.eval_calls: list[tuple[str, int]] = []
        self.sim_calls: list[tuple[object, ...]] = []
        self.close_calls: list[tuple[object, ...]] = []

    def eval(self, expression: str, nargout: int = 0) -> None:
        self.eval_calls.append((expression, nargout))

    def sim(self, *args, nargout: int = 1):
        self.sim_calls.append((*args, nargout))
        return "sim-output"

    def close_system(self, *args, nargout: int = 0) -> None:
        self.close_calls.append((*args, nargout))


def _load_simulate_module(monkeypatch):
    fake_matlab = types.SimpleNamespace(double=lambda value: ("matlab.double", value))
    monkeypatch.setitem(sys.modules, "matlab", fake_matlab)
    sys.modules.pop("backend.simulate_simulink", None)
    return importlib.import_module("backend.simulate_simulink")


def test_simulation_model_params_uses_smallest_sample_spacing(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)

    params = module.simulation_model_params(
        t_span=(0.0, 2.0),
        t_eval=[0.0, 0.25, 1.0, 2.0],
    )

    assert params["StartTime"] == "0.0"
    assert params["StopTime"] == "2.0"
    assert params["MaxStep"] == "0.25"
    assert params["OutputTimes"] == [0.0, 0.25, 1.0, 2.0]


def test_simulation_model_params_uses_t_span_when_only_one_sample(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)

    params = module.simulation_model_params(t_span=(1.0, 3.5), t_eval=[1.0])

    assert params["MaxStep"] == "2.5"


def test_prepare_workspace_variables_assigns_scalars_and_matrices(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()
    model_dict = {
        "name": "demo",
        "blocks": {
            "out": {"type": "Outport", "lib_path": "simulink/Ports & Subsystems/Out1"},
        },
        "outputs": [{"name": "y", "block": "out", "port": "1"}],
        "workspace_variables": {"gain_matrix": [[1.0, 2.0]], "bias": 4.0},
    }

    module.prepare_workspace_variables(engine, model_dict)

    assert engine.workspace["gain_matrix"] == ("matlab.double", [[1.0, 2.0]])
    assert engine.workspace["bias"] == 4.0
    assert engine.eval_calls == [
        ("assignin('base', 'gain_matrix', gain_matrix);", 0),
        ("assignin('base', 'bias', bias);", 0),
    ]


def test_simulate_simulink_model_builds_prepares_runs_and_extracts(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()
    normalized_model = {
        "name": "demo",
        "blocks": {"out": {"type": "Outport", "lib_path": "simulink/Ports & Subsystems/Out1"}},
        "outputs": [{"name": "y", "block": "out", "port": "1"}],
        "model_params": {"StopTime": "1"},
        "metadata": {"kind": "unit"},
    }
    prepare_calls: list[object] = []

    monkeypatch.setattr(module, "validate_simulink_model_dict", lambda model: normalized_model)
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda eng, model, output_dir=None, open_after_build=False: {
            "model_name": "demo",
            "model_file": "/tmp/demo.slx",
            "outputs": normalized_model["outputs"],
            "model_params": normalized_model["model_params"],
            "metadata": normalized_model["metadata"],
        },
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda eng, model: prepare_calls.append((eng, model)))
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda eng, sim_output, output_names: {
            "t": [0.0, 1.0],
            "states": [[1.0], [2.0]],
            "state_names": output_names,
            "signals": {"y": [1.0, 2.0]},
        },
    )

    result = module.simulate_simulink_model(engine, {"ignored": True}, output_dir="/tmp/build", open_after_build=True)

    assert prepare_calls == [(engine, normalized_model)]
    assert engine.sim_calls == [("demo", "ReturnWorkspaceOutputs", "on", 1)]
    assert result["model_name"] == "demo"
    assert result["state_names"] == ["y"]
    assert result["signals"]["y"] == [1.0, 2.0]


def test_execute_simulink_graph_returns_timings_and_validation(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    monkeypatch.setattr(
        module,
        "graph_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: {"model_name": "demo_model", "model_file": "/tmp/demo.slx"},
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]},
    )
    monkeypatch.setattr(
        module,
        "compare_simulink_results",
        lambda *args, **kwargs: {"passes": True, "vs_ode": {"rmse": 0.0, "max_abs_error": 0.0}},
    )

    result = module.execute_simulink_graph(
        engine,
        graph={"nodes": [], "edges": [], "state_chains": []},
        name="demo_model",
        state_names=["x"],
        parameter_values={"a": 1.0},
        initial_conditions={"x": 0.0},
        t_span=(0.0, 1.0),
        t_eval=[0.0, 1.0],
        ode_result={"t": [0.0]},
        tolerance=1e-6,
    )

    assert result.model_file == "/tmp/demo.slx"
    assert result.block_count == 1
    assert result.validation["passes"] is True
    assert result.build_time_sec >= 0.0
    assert result.simulation_time_sec >= 0.0


def test_execute_simulink_graph_raises_stage_aware_errors(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    monkeypatch.setattr(
        module,
        "graph_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("build boom")),
    )

    try:
        module.execute_simulink_graph(
            engine,
            graph={"nodes": [], "edges": [], "state_chains": []},
            name="demo_model",
            state_names=["x"],
            parameter_values={},
            initial_conditions={},
            t_span=(0.0, 1.0),
            t_eval=[0.0, 1.0],
        )
    except module.SimulinkExecutionStageError as exc:
        assert exc.stage == "simulink_build"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected SimulinkExecutionStageError")


def test_execute_simulink_descriptor_returns_timings(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    monkeypatch.setattr(
        module,
        "descriptor_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: {"model_name": "descriptor_model", "model_file": "/tmp/descriptor.slx"},
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]},
    )

    result = module.execute_simulink_descriptor(
        engine,
        descriptor_system={"form": "linear_descriptor"},
        name="descriptor_model",
        parameter_values={},
        differential_initial_conditions={"x": 0.0},
        algebraic_initial_conditions={"y": 0.0},
        t_span=(0.0, 1.0),
        t_eval=[0.0, 1.0],
    )

    assert result.model_file == "/tmp/descriptor.slx"
    assert result.validation is None
    assert result.block_count == 1
    assert result.build_time_sec >= 0.0
    assert result.simulation_time_sec >= 0.0


def test_execute_simulink_descriptor_raises_stage_aware_errors(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    monkeypatch.setattr(
        module,
        "descriptor_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("build boom")),
    )

    try:
        module.execute_simulink_descriptor(
            engine,
            descriptor_system={"form": "linear_descriptor"},
            name="descriptor_model",
            parameter_values={},
            differential_initial_conditions={"x": 0.0},
            algebraic_initial_conditions={"y": 0.0},
            t_span=(0.0, 1.0),
            t_eval=[0.0, 1.0],
        )
    except module.SimulinkExecutionStageError as exc:
        assert exc.stage == "simulink_build"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected SimulinkExecutionStageError")


def test_execute_simulink_graph_wraps_compare_and_validator_failures(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    monkeypatch.setattr(
        module,
        "graph_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: {"model_name": "demo_model", "model_file": "/tmp/demo.slx"},
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]},
    )
    monkeypatch.setattr(
        module,
        "compare_simulink_results",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("compare boom")),
    )

    with pytest.raises(module.SimulinkExecutionStageError) as compare_exc:
        module.execute_simulink_graph(
            engine,
            graph={"nodes": [], "edges": [], "state_chains": []},
            name="demo_model",
            state_names=["x"],
            parameter_values={},
            initial_conditions={},
            t_span=(0.0, 1.0),
            t_eval=[0.0, 1.0],
            ode_result={"t": [0.0]},
            tolerance=1e-6,
        )
    assert compare_exc.value.stage == "simulink_compare"

    with pytest.raises(module.SimulinkExecutionStageError) as validator_exc:
        module.execute_simulink_graph(
            engine,
            graph={"nodes": [], "edges": [], "state_chains": []},
            name="demo_model",
            state_names=["x"],
            parameter_values={},
            initial_conditions={},
            t_span=(0.0, 1.0),
            t_eval=[0.0, 1.0],
            numeric_result_validator=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad numeric")),
        )
    assert validator_exc.value.stage == "simulink_simulation"


def test_execute_simulink_graph_closes_model_when_requested(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    monkeypatch.setattr(
        module,
        "graph_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: {"model_name": "demo_model", "model_file": "/tmp/demo.slx"},
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]},
    )

    result = module.execute_simulink_graph(
        engine,
        graph={"nodes": [], "edges": [], "state_chains": []},
        name="demo_model",
        state_names=["x"],
        parameter_values={},
        initial_conditions={},
        t_span=(0.0, 1.0),
        t_eval=[0.0, 1.0],
        close_after_run=True,
    )

    assert result.model_name == "demo_model"
    assert engine.close_calls == [("demo_model", 0, 0)]


def test_execute_simulink_preserved_dae_graph_uses_algebraic_initials(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()
    captured_kwargs = {}

    def fake_graph_to_model(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return {"blocks": {"b1": {}}, "outputs": [{"name": "x"}, {"name": "z"}], "workspace_variables": {}}

    monkeypatch.setattr(module, "graph_to_simulink_model", fake_graph_to_model)
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: {"model_name": "dae_model", "model_file": "/tmp/dae.slx"},
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0, 0.0]], "state_names": ["x", "z"]},
    )

    result = module.execute_simulink_preserved_dae_graph(
        engine,
        graph={"nodes": [], "edges": [], "algebraic_chains": []},
        name="dae_model",
        output_names=["x", "z"],
        parameter_values={"k": 1.0},
        differential_initial_conditions={"x": 0.0},
        algebraic_initial_conditions={"z": 0.2},
        t_span=(0.0, 1.0),
        t_eval=[0.0, 1.0],
        close_after_run=True,
    )

    assert captured_kwargs["algebraic_initial_conditions"] == {"z": 0.2}
    assert result.model_file == "/tmp/dae.slx"
    assert engine.close_calls == [("dae_model", 0, 0)]


def test_execute_simulink_descriptor_close_errors_are_swallowed(monkeypatch) -> None:
    module = _load_simulate_module(monkeypatch)
    engine = FakeSimEngine()

    def close_boom(*args, **kwargs):
        raise RuntimeError("close boom")

    engine.close_system = close_boom  # type: ignore[method-assign]
    monkeypatch.setattr(
        module,
        "descriptor_to_simulink_model",
        lambda *args, **kwargs: {"blocks": {"b1": {}}, "outputs": [{"name": "x"}], "workspace_variables": {}},
    )
    monkeypatch.setattr(
        module,
        "build_simulink_model",
        lambda *args, **kwargs: {"model_name": "descriptor_model", "model_file": "/tmp/descriptor.slx"},
    )
    monkeypatch.setattr(module, "prepare_workspace_variables", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "extract_simulink_signals",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]},
    )

    result = module.execute_simulink_descriptor(
        engine,
        descriptor_system={"form": "linear_descriptor"},
        name="descriptor_model",
        parameter_values={},
        differential_initial_conditions={"x": 0.0},
        algebraic_initial_conditions={"y": 0.0},
        t_span=(0.0, 1.0),
        t_eval=[0.0, 1.0],
        close_after_run=True,
    )

    assert result.model_name == "descriptor_model"
