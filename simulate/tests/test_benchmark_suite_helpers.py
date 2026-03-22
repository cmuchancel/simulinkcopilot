from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.compilation import SymbolicCompilationStageError
from simulate import benchmark_suite as benchmark_module
from simulate.input_sources import detect_constant_input_values, sample_input_signals


def test_benchmark_suite_helper_functions_cover_sampling_and_failures() -> None:
    signal = benchmark_module.sinusoidal_input("u", amplitude=2.0, frequency=0.5, bias=1.0)
    assert signal(0.0)["u"] == 1.0

    case = benchmark_module.BenchmarkCase(
        name="demo",
        category="cat",
        latex=r"\dot{x}=u",
        input_function=lambda t: {"u": 2.0},
        expected_failure_stages=("parse",),
    )
    t_eval = benchmark_module._time_grid(case)
    assert t_eval.shape[0] == case.sample_count
    assert sample_input_signals(case.input_function, ["u"], t_eval)["u"]["values"][0] == 2.0
    assert detect_constant_input_values(case.input_function, ["u"], t_span=case.t_span) == {"u": 2.0}
    assert benchmark_module._check_expected_failure(case, "parse", "anything")

    varying = benchmark_module.BenchmarkCase(
        name="varying",
        category="cat",
        latex=r"\dot{x}=u",
        input_function=lambda t: {"u": t},
    )
    assert detect_constant_input_values(varying.input_function, ["u"], t_span=varying.t_span) is None
    substring_case = benchmark_module.BenchmarkCase(
        name="substring",
        category="cat",
        latex=r"\dot{x}=u",
        expected_failure_stages=("parse",),
        expected_failure_substring="expected",
    )
    assert not benchmark_module._check_expected_failure(substring_case, "parse", "different")


def test_finalize_case_handles_expected_failures_and_success_paths() -> None:
    metrics = {
        "state_count": 1,
        "graph_nodes": 2,
        "simulink_blocks": None,
        "ode_simulation_time_sec": 0.1,
        "state_space_simulation_time_sec": None,
        "simulink_build_time_sec": None,
        "simulink_simulation_time_sec": None,
    }
    case = benchmark_module.BenchmarkCase(
        name="bad",
        category="cat",
        latex=r"\int x dt",
        expected_failure_stages=("parse",),
    )
    result = benchmark_module._finalize_case(
        case,
        stages=benchmark_module._default_stages(),
        metrics=metrics,
        failure_stage="parse",
        failure_reason="boom",
    )
    assert result["overall_pass"] is True

    success_case = benchmark_module.BenchmarkCase(name="good", category="cat", latex=r"\dot{x}=-x")
    stages = benchmark_module._default_stages()
    for name in ["parse", "state_extraction", "solve", "first_order", "graph_lowering", "graph_validation", "ode_simulation"]:
        stages[name] = benchmark_module._stage("passed")
    stages["comparison"] = benchmark_module._stage("skipped")
    stages["simulink_compare"] = benchmark_module._stage("skipped")
    success = benchmark_module._finalize_case(
        success_case,
        stages=stages,
        metrics=metrics,
        equations=[],
        linearity={"is_linear": False, "A": 0, "B": 0, "offset": 0, "offending_entries": []},
        simulink_validation={"vs_ode": {"rmse": 0.0, "max_abs_error": 0.0}},
    )
    assert success["overall_pass"] is True
    markdown = benchmark_module.render_full_system_benchmark_markdown(
        {
            "generated_cases": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "tolerance": 1e-6,
            "cases": [result, success],
        }
    )
    assert "Full System Benchmark" in markdown
    assert "good" in markdown
    assert "failure_stage: parse" in markdown
    assert "failure_reason: boom" in markdown
    assert "simulink_metrics" in markdown


def test_run_full_system_benchmark_covers_engine_and_stage_failures(monkeypatch) -> None:
    monkeypatch.setattr(benchmark_module, "start_engine", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no matlab")))
    report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=True)
    case = report["cases"][0]
    assert case["stages"]["simulink_build"]["status"] == "failed"
    assert case["failure_stage"] == "simulink_build"

    monkeypatch.setattr(benchmark_module, "start_engine", lambda **kwargs: None)
    monkeypatch.setattr(
        benchmark_module,
        "compile_symbolic_system",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SymbolicCompilationStageError(
                "graph_lowering",
                "graph broke",
                completed_stages=("state_extraction", "solve", "first_order", "state_space"),
                linearity={"is_linear": True, "A": 0, "B": 0, "offset": 0, "offending_entries": []},
            )
        ),
    )
    report = benchmark_module.run_full_system_benchmark(selected_cases=["basic_decay"], run_simulink=False)
    case = report["cases"][0]
    assert case["stages"]["graph_lowering"]["status"] == "failed"
    assert case["failure_stage"] == "graph_lowering"


def test_write_full_system_benchmark_reports_writes_outputs(tmp_path: Path) -> None:
    report = benchmark_module.write_full_system_benchmark_reports(
        tmp_path,
        selected_cases=["basic_decay"],
        run_simulink=False,
    )
    assert report["generated_cases"] == 1
    assert (tmp_path / "full_system_benchmark.json").exists()
    assert (tmp_path / "full_system_benchmark.md").exists()
