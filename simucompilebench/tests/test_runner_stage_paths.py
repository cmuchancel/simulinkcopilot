from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.simulate_simulink import SimulinkExecutionResult, SimulinkExecutionStageError
from pipeline.compilation import SymbolicCompilationStageError, SymbolicCompilationResult
from simucompilebench import runner as runner_module
from simucompilebench.models import BenchmarkSystemSpec


def _spec(**overrides) -> BenchmarkSystemSpec:
    base = BenchmarkSystemSpec(
        system_id="controlled_feedback_pair",
        tier="T2",
        family="linear",
        latex=r"\dot{x}=-ax",
        generated_state_count=1,
        max_order=1,
        depth=1,
        includes_trig=False,
        nonlinear=False,
        parameter_values={"a": 1.0},
        initial_conditions={"x": 1.0},
        input_values={},
    )
    payload = base.__dict__ | overrides
    return BenchmarkSystemSpec(**payload)


@dataclass
class _FakeEngine:
    sim_result: object = field(default_factory=dict)
    quit_called: bool = False
    close_calls: list[str] = field(default_factory=list)
    close_raises: bool = False

    def sim(self, *args, **kwargs):
        return self.sim_result

    def close_system(self, model_name: str, *args, **kwargs) -> None:
        self.close_calls.append(model_name)
        if self.close_raises:
            raise RuntimeError("close boom")

    def quit(self) -> None:
        self.quit_called = True


@pytest.mark.parametrize(
    "stage",
    [
        "parse",
        "state_extraction",
        "solve",
        "first_order",
        "graph_validation",
        "ode_simulation",
    ],
)
def test_run_extended_benchmark_covers_stage_failures(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    if stage == "parse":
        monkeypatch.setattr(
            runner_module,
            "translate_latex",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")),
        )
    elif stage == "ode_simulation":
        monkeypatch.setattr(
            runner_module,
            "simulate_ode_system",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ode_simulation boom")),
        )
    elif stage == "graph_validation":
        monkeypatch.setattr(
            runner_module,
            "validate_graph_dict",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("graph_validation boom")),
        )
    else:
        completed_by_stage = {
            "state_extraction": (),
            "solve": ("state_extraction",),
            "first_order": ("state_extraction", "solve"),
        }
        monkeypatch.setattr(
            runner_module,
            "compile_symbolic_system",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                SymbolicCompilationStageError(
                    stage,
                    f"{stage} boom",
                    completed_stages=completed_by_stage[stage],
                )
            ),
        )
    report = runner_module.run_extended_benchmark([_spec()], run_simulink=False)
    system = report["systems"][0]
    assert system["failure_stage"] == stage
    assert system["stages"][stage]["status"] == "failed"


def test_run_extended_benchmark_covers_state_space_failure_and_compare_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner_module, "_robustness_score", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(runner_module, "validate_graph_dict", lambda graph: graph)
    monkeypatch.setattr(
        runner_module,
        "compile_symbolic_system",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SymbolicCompilationStageError(
                "state_space",
                "state space boom",
                completed_stages=("state_extraction", "solve", "first_order"),
            )
        ),
    )
    report = runner_module.run_extended_benchmark([_spec()], run_simulink=False)
    system = report["systems"][0]
    assert system["failure_stage"] == "state_space"
    assert system["stages"]["state_space"]["status"] == "failed"
    assert system["stages"]["state_space_simulation"]["status"] == "skipped"

    def _compiled_linear(*args, **kwargs):
        return SymbolicCompilationResult(
            equations=[],
            equation_dicts=[],
            extraction=type("Extraction", (), {"states": ("x",), "inputs": (), "parameters": (), "independent_variable": None})(),
            resolved_equations=[],
            solved_derivatives=[],
            first_order={"states": ["x"], "inputs": [], "parameters": [], "state_equations": [{"state": "x", "rhs": {"op": "symbol", "name": "x"}}]},
            explicit_form={"form": "explicit_first_order", "rhs": {"x": 0}},
            linearity={"is_linear": True},
            state_space={"A": [[-1.0]]},
            graph={"nodes": [{"id": "n1"}], "edges": []},
            validated_graph=None,
        )

    monkeypatch.setattr(runner_module, "compile_symbolic_system", _compiled_linear)
    monkeypatch.setattr(
        runner_module,
        "simulate_state_space_system",
        lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]},
    )
    monkeypatch.setattr(
        runner_module,
        "compare_simulations",
        lambda *args, **kwargs: {"passes": False, "rmse": 1.0, "max_abs_error": 2.0},
    )
    compare_report = runner_module.run_extended_benchmark([_spec()], run_simulink=False)
    compare_system = compare_report["systems"][0]
    assert compare_system["failure_stage"] == "state_space_compare"
    assert compare_system["stages"]["state_space_compare"]["status"] == "failed"


def test_run_extended_benchmark_covers_simulink_success_and_failure_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner_module, "_robustness_score", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(runner_module, "validate_graph_dict", lambda graph: graph)
    monkeypatch.setattr(
        runner_module,
        "compile_symbolic_system",
        lambda *args, **kwargs: SymbolicCompilationResult(
            equations=[],
            equation_dicts=[],
            extraction=type("Extraction", (), {"states": ("x",), "inputs": (), "parameters": (), "independent_variable": None})(),
            resolved_equations=[],
            solved_derivatives=[],
            first_order={"states": ["x"], "inputs": [], "parameters": [], "state_equations": [{"state": "x", "rhs": {"op": "symbol", "name": "x"}}]},
            explicit_form={"form": "explicit_first_order", "rhs": {"x": 0}},
            linearity={"is_linear": True},
            state_space={"A": [[-1.0]]},
            graph={"nodes": [{"id": "n1"}], "edges": []},
            validated_graph=None,
        ),
    )
    monkeypatch.setattr(runner_module, "simulate_state_space_system", lambda *args, **kwargs: {"t": [0.0], "states": [[0.0]], "state_names": ["x"]})
    monkeypatch.setattr(runner_module, "compare_simulations", lambda *args, **kwargs: {"passes": True, "rmse": 0.0, "max_abs_error": 0.0})
    monkeypatch.setattr(
        runner_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: SimulinkExecutionResult(
            model={"blocks": {"b1": {}}},
            simulation={"model_name": "demo_model", "model_file": "demo.slx"},
            validation={"passes": True, "vs_ode": {"rmse": 0.0, "max_abs_error": 0.0}},
            build_time_sec=0.1,
            simulation_time_sec=0.2,
        ),
    )

    build_fail_engine = _FakeEngine(sim_result=object())
    monkeypatch.setattr(runner_module, "start_engine", lambda **kwargs: build_fail_engine)
    monkeypatch.setattr(
        runner_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(SimulinkExecutionStageError("simulink_build", "build boom")),
    )
    build_fail_report = runner_module.run_extended_benchmark([_spec()], run_simulink=True)
    build_fail_system = build_fail_report["systems"][0]
    assert build_fail_system["failure_stage"] == "simulink_build"
    assert build_fail_system["stages"]["simulink_compare"]["status"] == "skipped"
    assert build_fail_engine.quit_called is True

    simulation_fail_engine = _FakeEngine()
    monkeypatch.setattr(runner_module, "start_engine", lambda **kwargs: simulation_fail_engine)
    monkeypatch.setattr(
        runner_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(SimulinkExecutionStageError("simulink_simulation", "sim boom")),
    )
    simulation_fail_report = runner_module.run_extended_benchmark([_spec()], run_simulink=True)
    simulation_fail_system = simulation_fail_report["systems"][0]
    assert simulation_fail_system["failure_stage"] == "simulink_simulation"

    compare_fail_engine = _FakeEngine()
    monkeypatch.setattr(runner_module, "start_engine", lambda **kwargs: compare_fail_engine)
    monkeypatch.setattr(
        runner_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: SimulinkExecutionResult(
            model={"blocks": {"b1": {}}},
            simulation={"model_name": "demo_model", "model_file": "demo.slx"},
            validation={"passes": False, "vs_ode": {"rmse": 1.0, "max_abs_error": 2.0}},
            build_time_sec=0.1,
            simulation_time_sec=0.2,
        ),
    )
    compare_fail_report = runner_module.run_extended_benchmark([_spec()], run_simulink=True)
    compare_fail_system = compare_fail_report["systems"][0]
    assert compare_fail_system["failure_stage"] == "simulink_compare"
    assert compare_fail_system["stages"]["simulink_compare"]["status"] == "failed"
    assert compare_fail_engine.quit_called is True
