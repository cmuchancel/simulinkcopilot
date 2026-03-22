from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from pipeline import matlab_bridge
from pipeline.run_pipeline import main


def test_run_matlab_bridge_request_rejects_invalid_request_and_options_shapes() -> None:
    with pytest.raises(Exception, match="JSON object"):
        matlab_bridge.run_matlab_bridge_request(["not", "a", "mapping"])  # type: ignore[arg-type]

    with pytest.raises(Exception, match="field 'options' must be an object"):
        matlab_bridge.run_matlab_bridge_request(
            {
                "source_type": "latex",
                "text": r"\dot{x}=-x",
                "options": ["bad"],
            }
        )

    with pytest.raises(Exception, match="must be an object"):
        matlab_bridge.run_matlab_bridge_request(
            {
                "source_type": "latex",
                "text": r"\dot{x}=-x",
                "options": {"runtime_override": "bad"},
            }
        )

    with pytest.raises(Exception, match="must be a non-empty string"):
        matlab_bridge.run_matlab_bridge_request(
            {
                "source_type": "latex",
                "text": r"\dot{x}=-x",
                "options": {"classification_mode": " "},
            }
        )


def test_run_matlab_bridge_request_returns_ok_response_for_explicit_ode() -> None:
    response = matlab_bridge.run_matlab_bridge_request(
        {
            "source_type": "matlab_symbolic",
            "equations": ["diff(x,t) == -x + u"],
            "states": ["x"],
            "inputs": ["u"],
            "time_variable": "t",
            "options": {
                "build": False,
                "run_sim": True,
                "runtime_override": {
                    "initial_conditions": {"x": 1.0},
                    "input_values": {"u": 0.0},
                    "t_span": [0.0, 0.5],
                    "sample_count": 6,
                },
            },
            "model_name": "bridge_demo",
        }
    )

    assert response["status"] == "ok"
    assert response["route"] == "explicit_ode"
    assert response["generated_model_path"] is None
    assert response["normalized_problem"]["source_type"] == "matlab_symbolic"
    assert response["artifacts"]["summary"]["source_type"] == "matlab_symbolic"
    assert response["validation"]["dae_validation"]["simulation_success"] is True


def test_run_matlab_bridge_request_accepts_missing_options_and_model_name_passthrough(monkeypatch) -> None:
    fake_results = {
        "dae_classification": {"kind": "explicit_ode"},
        "simulink_result": None,
        "dae_validation": {"simulation_success": True},
        "simulink_validation": None,
        "comparison": None,
        "consistent_initialization": SimpleNamespace(to_dict=lambda: {"ok": True}),
        "normalized_problem": SimpleNamespace(to_dict=lambda: {"source_type": "latex"}),
        "source_type": "latex",
    }
    captured: dict[str, object] = {}

    def fake_run_pipeline_payload(payload, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return fake_results

    monkeypatch.setattr("pipeline.run_pipeline.run_pipeline_payload", fake_run_pipeline_payload)
    monkeypatch.setattr("pipeline.run_pipeline.summarize_pipeline_results", lambda results: {"source_type": results["source_type"]})

    response = matlab_bridge.run_matlab_bridge_request(
        {
            "source_type": "latex",
            "text": r"\dot{x} = -x",
            "model_name": "bridge_demo",
        }
    )

    assert captured["payload"] == {
        "source_type": "latex",
        "text": r"\dot{x} = -x",
        "model_name": "bridge_demo",
        "name": "bridge_demo",
    }
    assert captured["kwargs"]["run_simulink"] is False
    assert response["status"] == "ok"
    assert response["request_echo"]["model_name"] == "bridge_demo"


def test_build_matlab_bridge_response_includes_generated_model_metadata(monkeypatch) -> None:
    monkeypatch.setattr("pipeline.run_pipeline.summarize_pipeline_results", lambda results: {"route": results["dae_classification"]["kind"]})

    response = matlab_bridge.build_matlab_bridge_response(
        {
            "dae_classification": {"kind": "linear_descriptor_dae"},
            "simulink_result": {"model_file": "/tmp/demo.slx", "model_name": "demo"},
            "dae_validation": None,
            "simulink_validation": {"matches": True},
            "comparison": None,
            "consistent_initialization": SimpleNamespace(to_dict=lambda: {"ok": True}),
            "normalized_problem": SimpleNamespace(to_dict=lambda: {"source_type": "matlab_symbolic"}),
            "source_type": "matlab_symbolic",
        }
    )

    assert response["generated_model_path"] == "/tmp/demo.slx"
    assert response["model_name"] == "demo"
    assert response["route"] == "linear_descriptor_dae"


def test_process_matlab_bridge_request_file_writes_error_response_for_opaque_ode_function(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    request_path.write_text(
        json.dumps(
            {
                "source_type": "matlab_ode_function",
                "function_spec": {"representation": "opaque_function_handle"},
                "states": ["x"],
                "options": {"build": False},
            }
        ),
        encoding="utf-8",
    )

    exit_code = matlab_bridge.process_matlab_bridge_request_file(request_path, response_path)
    response = json.loads(response_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert response["status"] == "error"
    assert response["error_code"] == "opaque_matlab_ode_function"
    assert "opaque function handles" in response["message"]


def test_process_matlab_bridge_request_file_writes_error_response_for_non_object_json(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    request_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    exit_code = matlab_bridge.process_matlab_bridge_request_file(request_path, response_path, verbose=True)
    response = json.loads(response_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert response["status"] == "error"
    assert response["error_code"] == "deterministic_compile_error"
    assert "must decode to an object" in response["message"]
    assert response["request_echo"] is None


def test_main_request_mode_writes_response_json(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    request_path.write_text(
        json.dumps(
            {
                "source_type": "matlab_equation_text",
                "equations": ["xdot = z", "0 = z + sin(x)"],
                "states": ["x"],
                "algebraics": ["z"],
                "options": {
                    "build": False,
                    "run_sim": True,
                    "runtime_override": {
                        "initial_conditions": {"x": 0.2},
                        "t_span": [0.0, 0.25],
                        "sample_count": 5,
                    },
                },
                "model_name": "request_mode_demo",
            }
        ),
        encoding="utf-8",
    )

    argv = [
        "run_pipeline.py",
        "--request",
        str(request_path),
        "--response",
        str(response_path),
    ]
    with mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()):
        exit_code = main()

    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert response["status"] == "ok"
    assert response["route"] == "reducible_semi_explicit_dae"
    assert response["generated_model_path"] is None


def test_main_request_mode_requires_response_path(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["run_pipeline.py", "--request", "req.json"])
    with pytest.raises(SystemExit):
        main()


def test_build_matlab_bridge_error_response_verbose_includes_traceback() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        response = matlab_bridge.build_matlab_bridge_error_response(
            exc,
            request={"source_type": "latex"},
            verbose=True,
        )

    assert response["status"] == "error"
    assert response["source_type"] == "latex"
    assert any("Traceback" in item for item in response["diagnostics"])


@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (RuntimeError("opaque function handles are unsupported"), "opaque_matlab_ode_function"),
        (RuntimeError("could not determine whether 'xdot' is a state derivative or an ordinary variable"), "ambiguous_derivative_alias"),
        (RuntimeError("structurally singular"), "unsupported_algebraic_subsystem"),
        (RuntimeError("must declare exactly one independent variable"), "invalid_independent_variable"),
    ],
)
def test_bridge_error_code_maps_specific_messages(exc: Exception, expected_code: str) -> None:
    assert matlab_bridge._bridge_error_code(exc) == expected_code


def test_optional_string_option_accepts_clean_string_and_rejects_non_string() -> None:
    assert matlab_bridge._optional_string_option({"classification_mode": " strict "}, "classification_mode") == "strict"
    with pytest.raises(Exception, match="must be a non-empty string"):
        matlab_bridge._optional_string_option({"classification_mode": 3}, "classification_mode")  # type: ignore[arg-type]
