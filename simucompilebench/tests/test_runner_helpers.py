from __future__ import annotations

from pathlib import Path

import pytest

from simucompilebench import runner as runner_module
from simucompilebench.models import BenchmarkSystemSpec


def _spec(**overrides) -> BenchmarkSystemSpec:
    base = BenchmarkSystemSpec(
        system_id="demo",
        tier="T1",
        family="family",
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


def test_runner_helper_functions_cover_failure_mapping_and_fault_injection() -> None:
    assert runner_module._mean([1.0, None, 3.0]) == 2.0
    assert runner_module._mean([None]) is None

    runner_module._validate_numeric_result("ok", {"states": [[1.0], [2.0]]})
    with pytest.raises(RuntimeError, match="non-finite state values"):
        runner_module._validate_numeric_result("bad", {"states": [[1.0], [float("nan")]]})

    assert runner_module._failure_category("parse", "bad parse") == "parse_failure"
    assert runner_module._failure_category("simulink_compare", "contains nan") == "numerical_instability"
    assert runner_module._failure_category("simulink_build", "oops") == "simulink_failure"

    graph = {"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": [{"source": "n1", "dst": "n2"}]}
    assert runner_module._inject_graph_fault(graph, None) is graph
    dropped = runner_module._inject_graph_fault(graph, "drop_node")
    assert len(dropped["nodes"]) == 1
    assert runner_module._inject_graph_fault({"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": []}, "drop_node") == {
        "nodes": [{"id": "n1"}, {"id": "n2"}],
        "edges": [],
    }
    assert runner_module._inject_graph_fault({"nodes": [{"id": "n1"}], "edges": []}, "drop_node") == {
        "nodes": [{"id": "n1"}],
        "edges": [],
    }
    with pytest.raises(RuntimeError, match="Unsupported graph fault injection"):
        runner_module._inject_graph_fault(graph, "bad")

    spec = _spec(expected_failure_stage="parse", expected_failure_substring="oops")
    assert runner_module._match_expected_failure(spec, "parse", "oops happened") is True
    assert runner_module._match_expected_failure(spec, "solve", "oops happened") is False
    assert runner_module._match_expected_failure(_spec(expected_failure_stage="parse"), "parse", "anything") is True


def test_robustness_score_and_result_row_cover_success_and_expected_failure(monkeypatch) -> None:
    spec = _spec()
    first_order = {"states": ["x"]}
    monkeypatch.setattr(
        runner_module,
        "simulate_ode_system",
        lambda *args, **kwargs: {"t": [0.0, 1.0], "states": [[0.0], [1.0]], "state_names": ["x"]},
    )
    monkeypatch.setattr(
        runner_module,
        "simulate_state_space_system",
        lambda *args, **kwargs: {"t": [0.0, 1.0], "states": [[0.0], [1.0]], "state_names": ["x"]},
    )
    monkeypatch.setattr(runner_module, "compare_simulations", lambda *args, **kwargs: {"passes": True})
    assert runner_module._robustness_score(spec, first_order, state_space={"A": 1}, tolerance=1e-6) == 1.0
    assert runner_module._robustness_score(spec, first_order, state_space=None, tolerance=1e-6) == 1.0
    monkeypatch.setattr(runner_module, "compare_simulations", lambda *args, **kwargs: {"passes": False})
    assert runner_module._robustness_score(spec, first_order, state_space={"A": 1}, tolerance=1e-6) == 0.0
    monkeypatch.setattr(
        runner_module,
        "simulate_ode_system",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert runner_module._robustness_score(spec, first_order, state_space=None, tolerance=1e-6) == 0.0
    assert runner_module._robustness_score(spec, {"states": []}, state_space=None, tolerance=1e-6) is None

    stages = runner_module._default_stages()
    for name in ["parse", "state_extraction", "solve", "first_order", "graph_lowering", "graph_validation", "ode_simulation"]:
        stages[name] = runner_module._stage("passed")
    stages["state_space"] = runner_module._stage("skipped")
    stages["state_space_simulation"] = runner_module._stage("skipped")
    stages["state_space_compare"] = runner_module._stage("skipped")
    stages["simulink_build"] = runner_module._stage("skipped")
    stages["simulink_simulation"] = runner_module._stage("skipped")
    stages["simulink_compare"] = runner_module._stage("skipped")

    success = runner_module._result_row(
        spec,
        stages=stages,
        failure_stage=None,
        failure_reason=None,
        normalized_equations=["x'=-ax"],
        extracted_state_count=1,
        graph_node_count=3,
        simulink_block_count=None,
        state_space_available=False,
        ode_simulation_time_sec=0.1,
        state_space_simulation_time_sec=None,
        simulink_build_time_sec=None,
        simulink_simulation_time_sec=None,
        state_space_rmse=None,
        state_space_max_abs_error=None,
        simulink_rmse=None,
        simulink_max_abs_error=None,
        robustness_score=1.0,
    )
    assert success["overall_pass"] is True
    assert success["benchmark_result"] == "pass"

    expected_failure = runner_module._result_row(
        _spec(expected_failure_stage="parse", expected_failure_substring="bad", expected_failure_category="parse_failure"),
        stages=runner_module._default_stages(),
        failure_stage="parse",
        failure_reason="bad parse",
        normalized_equations=None,
        extracted_state_count=None,
        graph_node_count=None,
        simulink_block_count=None,
        state_space_available=False,
        ode_simulation_time_sec=None,
        state_space_simulation_time_sec=None,
        simulink_build_time_sec=None,
        simulink_simulation_time_sec=None,
        state_space_rmse=None,
        state_space_max_abs_error=None,
        simulink_rmse=None,
        simulink_max_abs_error=None,
        robustness_score=None,
    )
    assert expected_failure["benchmark_result"] == "expected_failure_observed"
    assert expected_failure["failure_category"] == "parse_failure"


def test_unexpected_failure_helpers_cover_stage_inference_and_marking() -> None:
    spec = _spec()
    stages = runner_module._default_stages()
    for name in ["parse", "state_extraction", "solve", "first_order", "graph_lowering", "graph_validation", "ode_simulation"]:
        stages[name] = runner_module._stage("passed")
    stages["state_space"] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(stages, run_simulink=False, spec=spec) == "state_space_simulation"

    stages["state_space_simulation"] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(stages, run_simulink=False, spec=spec) == "state_space_compare"

    stages["state_space_compare"] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(stages, run_simulink=True, spec=spec) == "simulink_build"
    assert runner_module._mark_unexpected_failure(stages, "boom", run_simulink=True, spec=spec) == "simulink_build"
    assert stages["simulink_simulation"]["detail"] == "Simulink build failed"

    stages = runner_module._default_stages()
    for name in [
        "parse",
        "state_extraction",
        "solve",
        "first_order",
        "graph_lowering",
        "graph_validation",
        "ode_simulation",
        "simulink_build",
    ]:
        stages[name] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(stages, run_simulink=True, spec=spec) == "simulink_simulation"
    assert runner_module._mark_unexpected_failure(stages, "sim boom", run_simulink=True, spec=spec) == "simulink_simulation"
    assert stages["simulink_compare"]["detail"] == "Simulink simulation failed"

    stages["simulink_simulation"] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(stages, run_simulink=True, spec=spec) == "simulink_compare"
    stages["simulink_compare"] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(stages, run_simulink=True, spec=spec) == "other"

    expected_failure_spec = _spec(expected_failure_stage="parse")
    assert runner_module._infer_unexpected_failure_stage(
        runner_module._default_stages(),
        run_simulink=False,
        spec=expected_failure_spec,
    ) == "parse"

    other_stages = runner_module._default_stages()
    for name in [
        "parse",
        "state_extraction",
        "solve",
        "first_order",
        "graph_lowering",
        "graph_validation",
        "ode_simulation",
    ]:
        other_stages[name] = runner_module._stage("passed")
    assert runner_module._infer_unexpected_failure_stage(other_stages, run_simulink=False, spec=spec) == "other"
    assert runner_module._mark_unexpected_failure(other_stages, "other boom", run_simulink=False, spec=spec) == "other"


def test_runner_report_aggregation_and_writers_cover_outputs(tmp_path: Path) -> None:
    systems = [
        {
            "system_id": "s1",
            "tier": "T1",
            "family": "fam",
            "generated_state_count": 1,
            "order": 1,
            "depth": 1,
            "nonlinear": False,
            "trig": False,
            "expected_failure": False,
            "state_space_available": True,
            "normalized_equations": ["eq1"],
            "extracted_state_count": 1,
            "graph_node_count": 3,
            "simulink_block_count": 4,
            "ode_simulation_time_sec": 0.1,
            "state_space_simulation_time_sec": 0.1,
            "build_time_sec": 0.2,
            "simulation_time_sec": 0.3,
            "rmse": 0.01,
            "max_abs_error": 0.02,
            "state_space_rmse": 0.01,
            "state_space_max_abs_error": 0.02,
            "simulink_rmse": None,
            "simulink_max_abs_error": None,
            "robustness_score": 1.0,
            "failure_stage": None,
            "failure_reason": None,
            "failure_category": None,
            "benchmark_result": "pass",
            "overall_pass": True,
            "stages": {"parse": {"status": "passed", "detail": None}},
        },
        {
            "system_id": "s2",
            "tier": "T2",
            "family": "fam",
            "generated_state_count": 2,
            "order": 2,
            "depth": 2,
            "nonlinear": True,
            "trig": True,
            "expected_failure": False,
            "state_space_available": False,
            "normalized_equations": ["eq2"],
            "extracted_state_count": 2,
            "graph_node_count": 5,
            "simulink_block_count": None,
            "ode_simulation_time_sec": 0.2,
            "state_space_simulation_time_sec": None,
            "build_time_sec": None,
            "simulation_time_sec": None,
            "rmse": None,
            "max_abs_error": None,
            "state_space_rmse": None,
            "state_space_max_abs_error": None,
            "simulink_rmse": None,
            "simulink_max_abs_error": None,
            "robustness_score": None,
            "failure_stage": "parse",
            "failure_reason": "bad parse",
            "failure_category": "parse_failure",
            "benchmark_result": "unexpected_failure",
            "overall_pass": False,
            "stages": {"parse": {"status": "failed", "detail": "bad parse"}},
        },
    ]
    report = runner_module._aggregate_report(systems, tolerance=1e-6, report_name="demo")
    assert report["passed_systems"] == 1
    assert report["failed_systems"] == 1
    assert report["failure_categories"]["parse_failure"] == 1

    csv_rows = runner_module._csv_rows(report)
    assert csv_rows[0]["system_id"] == "s1"

    markdown = runner_module.render_simucompilebench_markdown(
        report | {"baseline_comparison": {"matches": True, "mismatches": []}}
    )
    assert "SimuCompileBench" in markdown
    assert "s1" in markdown

    written = runner_module.write_simucompilebench_reports(
        report | {"baseline_comparison": {"matches": True, "mismatches": []}},
        output_dir=tmp_path,
    )
    assert written["name"] == "demo"
    assert (tmp_path / "simucompilebench.json").exists()
    assert (tmp_path / "simucompilebench.md").exists()
    assert (tmp_path / "simucompilebench.csv").exists()

    legacy_report = {
        "evaluated_systems": 1,
        "passed_systems": 1,
        "failed_systems": 0,
        "average_rmse": 0.01,
        "average_max_abs_error": 0.02,
        "systems": [
            {
                "system_id": "legacy",
                "state_space_success": True,
                "normalized_equations": ["eq"],
                "extracted_state_count": 1,
                "graph_node_count": 3,
                "simulink_block_count": 4,
                "ode_simulation_time_sec": 0.1,
                "state_space_simulation_time_sec": 0.1,
                "build_time_sec": 0.2,
                "simulation_time_sec": 0.3,
                "rmse": 0.01,
                "max_abs_error": 0.02,
                "state_space_rmse": 0.01,
                "state_space_max_abs_error": 0.02,
                "simulink_rmse": None,
                "simulink_max_abs_error": None,
                "failure_stage": None,
                "failure_reason": None,
                "overall_pass": True,
                "stages": {"parse": {"status": "passed", "detail": None}},
            }
        ],
    }
    legacy_spec = _spec(system_id="legacy", tier="legacy", family="legacy")
    combined = runner_module.combine_benchmark_results(
        legacy_report=legacy_report,
        legacy_specs=[legacy_spec],
        extended_report=report,
        dataset_manifest={"systems": 3},
        baseline_comparison={"matches": True, "mismatches": []},
    )
    assert combined["dataset_manifest"] == {"systems": 3}


def test_runner_markdown_and_report_writers_cover_empty_sections(tmp_path: Path) -> None:
    report = {
        "name": "empty",
        "evaluated_systems": 0,
        "passed_systems": 0,
        "failed_systems": 0,
        "tolerance": 1e-6,
        "baseline_comparison": {"matches": False, "mismatches": ["case_a"]},
        "tier_summary": {},
        "failure_categories": {},
        "average_rmse": None,
        "median_rmse": None,
        "max_rmse": None,
        "average_max_abs_error": None,
        "max_abs_error": None,
        "average_robustness_score": None,
        "complexity_by_generated_state_count": {},
        "systems": [],
    }

    markdown = runner_module.render_simucompilebench_markdown(report)
    assert "- mismatch: case_a" in markdown
    assert "- none" in markdown

    written = runner_module.write_simucompilebench_reports(report, output_dir=tmp_path)
    assert written["name"] == "empty"
    assert (tmp_path / "simucompilebench.csv").read_text(encoding="utf-8") == ""


def test_run_extended_benchmark_reports_engine_failure_and_progress(monkeypatch) -> None:
    spec = _spec(system_id="controlled_feedback_pair")
    progress_events: list[tuple[int, int, str]] = []
    monkeypatch.setattr(runner_module, "start_engine", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no matlab")))
    report = runner_module.run_extended_benchmark(
        [spec],
        run_simulink=True,
        progress_callback=lambda index, total, result: progress_events.append((index, total, result["system_id"])),
    )
    assert report["evaluated_systems"] == 1
    assert progress_events == [(1, 1, "controlled_feedback_pair")]
