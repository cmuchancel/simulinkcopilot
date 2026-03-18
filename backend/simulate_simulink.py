"""Simulate backend-generated Simulink models and extract signals."""

from __future__ import annotations

from pathlib import Path

import matlab
import numpy as np

from backend.builder import build_simulink_model
from backend.extract_signals import extract_simulink_signals
from backend.simulink_dict import BackendSimulinkModelDict, validate_simulink_model_dict


def simulation_model_params(
    *,
    t_span: tuple[float, float],
    t_eval,
    solver: str = "ode45",
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-12,
) -> dict[str, object]:
    """Return deterministic model parameters for Simulink simulation."""
    t_eval = np.asarray(t_eval, dtype=float)
    max_step = float(np.min(np.diff(t_eval))) if t_eval.size > 1 else float(t_span[1] - t_span[0])
    return {
        "StartTime": str(float(t_span[0])),
        "StopTime": str(float(t_span[1])),
        "Solver": solver,
        "RelTol": repr(float(rel_tol)),
        "AbsTol": repr(float(abs_tol)),
        "MaxStep": repr(max_step),
        "OutputOption": "SpecifiedOutputTimes",
        "OutputTimes": [float(value) for value in t_eval.tolist()],
        "SaveOutput": "on",
        "OutputSaveName": "yout",
        "SaveFormat": "StructureWithTime",
    }


def prepare_workspace_variables(eng, model_dict: BackendSimulinkModelDict | dict[str, object]) -> None:
    """Populate MATLAB workspace variables required by a backend model dictionary."""
    normalized = validate_simulink_model_dict(model_dict)
    for name, value in normalized.get("workspace_variables", {}).items():
        if (
            isinstance(value, list)
            and value
            and all(isinstance(row, list) for row in value)
        ):
            eng.workspace[name] = matlab.double(value)
        else:
            eng.workspace[name] = value
        eng.eval(f"assignin('base', '{name}', {name});", nargout=0)


def simulate_simulink_model(
    eng,
    model_dict: BackendSimulinkModelDict | dict[str, object],
    *,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
) -> dict[str, object]:
    """Build, simulate, and extract a backend-generated Simulink model."""
    normalized = validate_simulink_model_dict(model_dict)
    build_info = build_simulink_model(
        eng,
        normalized,
        output_dir=output_dir,
        open_after_build=open_after_build,
    )
    prepare_workspace_variables(eng, normalized)
    sim_output = eng.sim(build_info["model_name"], "ReturnWorkspaceOutputs", "on", nargout=1)
    extracted = extract_simulink_signals(
        eng,
        sim_output,
        output_names=[entry["name"] for entry in normalized["outputs"]],
    )
    return {
        **build_info,
        **extracted,
    }
