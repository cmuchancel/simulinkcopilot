from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.simulate_simulink import SimulinkExecutionResult, SimulinkExecutionStageError
from pipeline.compilation import SymbolicCompilationStageError
from simulate import benchmark_suite as benchmark_module


@dataclass
class _FakeEngine:
    sim_result: object = field(default_factory=dict)
    quit_called: bool = False

    def sim(self, *args, **kwargs):
        return self.sim_result

    def quit(self) -> None:
        self.quit_called = True


@pytest.mark.parametrize(
    "stage",
    [
        "parse",
        "state_extraction",
        "solve",
        "first_order",
        "state_space",
        "graph_validation",
        "ode_simulation",
    ],
)
def test_run_full_system_benchmark_covers_unexpected_stage_failures(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    if stage == "parse":
        monkeypatch.setattr(
            benchmark_module,
            "translate_latex",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")),
        )
    elif stage == "ode_simulation":
        monkeypatch.setattr(
            benchmark_module,
            "simulate_ode_system",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ode_simulation boom")),
        )
    else:
        completed_by_stage = {
            "state_extraction": (),
            "solve": ("state_extraction",),
            "first_order": ("state_extraction", "solve"),
            "state_space": ("state_extraction", "solve", "first_order"),
            "graph_validation": ("state_extraction", "solve", "first_order", "state_space", "graph_lowering"),
        }
        monkeypatch.setattr(
            benchmark_module,
            "compile_symbolic_system",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                SymbolicCompilationStageError(
                    stage,
                    f"{stage} boom",
                    completed_stages=completed_by_stage[stage],
                    linearity={"is_linear": True, "A": 0, "B": 0, "offset": 0, "offending_entries": []}
                    if stage == "graph_validation"
                    else None,
                )
            ),
        )
    report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=False)
    case = report["cases"][0]
    assert case["failure_stage"] == stage
    assert case["stages"][stage]["status"] == "failed"


def test_run_full_system_benchmark_covers_state_space_comparison_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark_module,
        "compare_simulations",
        lambda *args, **kwargs: {"passes": False, "rmse": 1.0, "max_abs_error": 2.0},
    )
    report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=False)
    case = report["cases"][0]
    assert case["stages"]["comparison"]["status"] == "failed"
    assert case["overall_pass"] is False


def test_run_full_system_benchmark_covers_state_space_comparison_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark_module,
        "compare_simulations",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("compare boom")),
    )
    report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=False)
    case = report["cases"][0]
    assert case["failure_stage"] == "comparison"
    assert case["stages"]["comparison"]["status"] == "failed"


def test_run_full_system_benchmark_covers_simulink_success_and_variable_input_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine(sim_result=object())
    monkeypatch.setattr(benchmark_module, "start_engine", lambda **kwargs: engine)
    monkeypatch.setattr(
        benchmark_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: SimulinkExecutionResult(
            model={"blocks": {"b1": {}}},
            simulation={"model_name": "demo_model", "model_file": "demo.slx"},
            validation={"passes": True, "vs_ode": {"rmse": 0.0, "max_abs_error": 0.0}},
            build_time_sec=0.1,
            simulation_time_sec=0.2,
        ),
    )

    report = benchmark_module.run_full_system_benchmark(selected_cases=["driven_mass_spring"], run_simulink=True)
    case = report["cases"][0]
    assert case["stages"]["simulink_build"]["status"] == "passed"
    assert case["stages"]["simulink_simulation"]["status"] == "passed"
    assert case["stages"]["simulink_compare"]["status"] == "passed"
    assert case["metrics"]["simulink_blocks"] == 1
    assert engine.quit_called is True


def test_run_full_system_benchmark_covers_simulink_build_and_compare_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(benchmark_module, "start_engine", lambda **kwargs: _FakeEngine(sim_result=object()))
    monkeypatch.setattr(
        benchmark_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(SimulinkExecutionStageError("simulink_build", "build boom")),
    )
    build_fail_report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=True)
    build_fail_case = build_fail_report["cases"][0]
    assert build_fail_case["failure_stage"] == "simulink_build"
    assert build_fail_case["stages"]["simulink_compare"]["status"] == "skipped"

    monkeypatch.setattr(
        benchmark_module,
        "execute_simulink_graph",
        lambda *args, **kwargs: SimulinkExecutionResult(
            model={"blocks": {"b1": {}}},
            simulation={"model_name": "demo_model", "model_file": "demo.slx"},
            validation={"passes": False, "vs_ode": {"rmse": 1.0, "max_abs_error": 2.0}},
            build_time_sec=0.1,
            simulation_time_sec=0.2,
        ),
    )
    compare_fail_report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=True)
    compare_fail_case = compare_fail_report["cases"][0]
    assert compare_fail_case["stages"]["simulink_compare"]["status"] == "failed"
    assert compare_fail_case["overall_pass"] is False
