from __future__ import annotations

import json
from pathlib import Path

import pytest

from eqn2sim_gui import app as app_module
from eqn2sim_gui.model_metadata import GuiModelMetadata


def _metadata() -> GuiModelMetadata:
    return GuiModelMetadata(
        latex=r"m\ddot{x}+kx=0",
        normalized_latex=r"m\ddot{x}+kx=0",
        equations=["D2_x*m + k*x = 0"],
        symbols={
            "m": {"role": "parameter", "description": "", "units": "", "value": 2.0, "input_kind": "constant"},
            "k": {"role": "parameter", "description": "", "units": "", "value": 3.0, "input_kind": "constant"},
            "x": {"role": "state", "description": "", "units": "", "value": None, "input_kind": "constant"},
        },
        initial_conditions={"x": 1.0, "x_dot": 0.0},
        extracted_states=["x", "x_dot"],
        derivative_orders={"x": 2},
    )


def test_debug_trace_and_run_name_helpers(tmp_path: Path) -> None:
    assert app_module._resolve_debug_request_id("abc123def456") == "abc123def456"
    generated = app_module._resolve_debug_request_id("bad")
    assert len(generated) == 12

    trace = app_module._open_debug_trace(
        tmp_path,
        request_id="abc123def456",
        action="draft_structured",
        raw_text="raw text",
        latex_text="x=1",
    )
    trace.record("midpoint", ok=True)
    trace.finish()
    payload = json.loads((tmp_path / "abc123def456.json").read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["events"][0]["stage"] == "request_received"

    fail_trace = app_module._RequestDebugTrace(
        request_id="deadbeefcafe",
        path=tmp_path / "deadbeefcafe.json",
        action="draft_structured",
    )
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        fail_trace.fail("failed_stage", exc)
    fail_payload = json.loads((tmp_path / "deadbeefcafe.json").read_text(encoding="utf-8"))
    assert fail_payload["status"] == "failed"
    assert fail_payload["error_message"] == "boom"

    artifact_dir = app_module._artifact_dir(tmp_path, "x=1")
    assert artifact_dir.name.startswith("run_")
    assert app_module._is_valid_run_name("run_deadbeefcafe")
    assert app_module._is_valid_run_name("run_20260320_101500_deadbeefcafe_abc123")
    assert not app_module._is_valid_run_name("bad_run")


def test_recent_run_listing_and_run_browser_context(tmp_path: Path) -> None:
    valid_run = tmp_path / "run_20260320_101500_deadbeefcafe_abc123"
    valid_run.mkdir()
    (valid_run / "gui_metadata.json").write_text(
        json.dumps({"latex": r"m\ddot{x}+kx=0", "equations": ["eq1", "eq2"]}),
        encoding="utf-8",
    )
    (valid_run / "demo.slx").write_bytes(b"slx")
    invalid_run = tmp_path / "not_a_run"
    invalid_run.mkdir()

    app = app_module.create_app()
    with app.test_request_context("/"):
        recent = app_module._list_recent_runs(tmp_path)
        assert len(recent) == 1
        assert recent[0]["run_name"] == valid_run.name
        assert recent[0]["equation_count"] == 2

        context = {"recent_runs": recent, "active_run_name": valid_run.name}
        app_module._apply_run_browser_context(context)
        assert context["active_run_index"] == 0
        assert context["active_run_download_url"] == recent[0]["download_url"]


def test_saved_run_loading_and_action_aliases(monkeypatch, tmp_path: Path) -> None:
    app = app_module.create_app()
    run_name = "run_20260320_101500_deadbeefcafe_abc123"
    run_dir = tmp_path / run_name
    run_dir.mkdir()
    (run_dir / "gui_metadata.json").write_text(json.dumps(_metadata().to_dict()), encoding="utf-8")
    (run_dir / "validated_model_spec.json").write_text("{}", encoding="utf-8")
    (run_dir / "simulink_model_dict.json").write_text("{}", encoding="utf-8")
    (run_dir / f"{run_name}.slx").write_bytes(b"slx")
    monkeypatch.setattr(app_module, "_load_or_generate_state_trajectory_artifacts", lambda metadata, artifact_dir: {"state_trajectory_svg": None})

    with app.test_request_context("/"):
        loaded = app_module._load_saved_run_context(tmp_path, run_name)
    assert loaded["download_url"].endswith(run_name)
    assert loaded["summary"]["states"] == ["x", "x_dot"]
    assert app_module._normalize_action("draft") == "draft_structured"
    assert app_module._normalize_action("refresh") == "refresh_equations"
    assert app_module._normalize_action("run") == "generate_model"


def test_symbol_seed_and_readiness_helpers_cover_blockers() -> None:
    merged = app_module._merge_seeded_symbol_values({"m": {"value": 1.0}}, {"m": {"role": "parameter"}, "x": {"role": "state"}})
    assert merged["m"] == {"value": 1.0, "role": "parameter"}
    assert app_module._extract_seedable_symbol_name(r"\phi_e = \pi R^2") == "phi_e"
    assert app_module._extract_seedable_symbol_name(r"\cos\theta \approx 0.7") is None
    assert app_module._extract_numeric_value_hint(r"\phi_e \approx 1.77 \times 10^{-8}") == pytest.approx(1.77e-8)
    assert app_module._extract_numeric_value_hint("nothing useful") is None

    readiness = app_module._evaluate_generation_readiness(
        [{"name": "x", "max_derivative_order": 2}, {"name": "m", "max_derivative_order": 0}],
        {
            "x": {"role": "parameter", "value": ""},
            "m": {"role": "parameter", "value": "abc"},
        },
        ["x", "x_dot"],
        {"x": "", "x_dot": "bad"},
    )
    assert readiness["ready"] is False
    assert any("must stay marked as a state" in blocker for blocker in readiness["blockers"])
    assert any("numeric value" in blocker for blocker in readiness["blockers"])
    assert any("initial condition" in blocker for blocker in readiness["blockers"])


def test_metadata_persistence_and_trajectory_artifact_loading(monkeypatch, tmp_path: Path) -> None:
    metadata = _metadata()
    built = app_module._build_validated_metadata(
        latex_text=metadata.latex,
        normalized_latex=metadata.normalized_latex,
        equation_strings=metadata.equations,
        symbol_values=metadata.symbols,
        state_initials={"x": "1.0", "x_dot": "0.0"},
        state_chain=["x", "x_dot"],
        derivative_orders={"x": 2},
    )
    assert built.initial_conditions == {"x": 1.0, "x_dot": 0.0}

    persisted = app_module._persist_validated_representation(tmp_path, metadata)
    assert Path(persisted["metadata_path"]).exists()
    assert Path(persisted["validated_spec_path"]).exists()

    plot_path, data_path = app_module._simulation_artifact_paths(persisted["artifact_dir_path"])
    plot_path.write_text("<svg></svg>", encoding="utf-8")
    data_path.write_text(
        json.dumps(
            {
                "t_span": [0.0, 1.0],
                "state_names": ["x"],
                "series": [{"label": "ODE", "t": [0.0, 1.0], "states": {"x": [1.0, 0.0]}}],
                "simulink_error": "missing overlay",
            }
        ),
        encoding="utf-8",
    )
    loaded = app_module._load_state_trajectory_artifacts(persisted["artifact_dir_path"])
    assert loaded["state_trajectory_plot_path"] == str(plot_path.resolve())
    assert loaded["state_trajectory_summary"]["simulink_available"] is False

    (persisted["artifact_dir_path"] / "demo.slx").write_bytes(b"slx")
    monkeypatch.setattr(app_module, "_generate_state_trajectory_artifacts", lambda metadata, artifact_dir: {"generated": True})
    regenerated = app_module._load_or_generate_state_trajectory_artifacts(metadata, persisted["artifact_dir_path"])
    assert regenerated == {"generated": True}
