from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import pytest

from pipeline import matlab_bridge
from pipeline.run_pipeline import main


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
