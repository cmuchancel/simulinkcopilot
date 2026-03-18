"""MATLAB-backed Simulink model builder for backend model dictionaries."""

from __future__ import annotations

from pathlib import Path

import matlab

from backend.simulink_dict import BackendSimulinkModelDict, validate_simulink_model_dict
from simulink.builder import build_model as build_core_model
from simulink.utils import matlab_param_value, sanitize_block_name


def _assign_workspace_value(eng, name: str, value: object) -> None:
    if (
        isinstance(value, list)
        and value
        and all(isinstance(row, list) for row in value)
    ):
        eng.workspace[name] = matlab.double(value)
    else:
        eng.workspace[name] = value
    eng.eval(f"assignin('base', '{name}', {name});", nargout=0)


def build_simulink_model(
    eng,
    model_dict: BackendSimulinkModelDict | dict[str, object],
    *,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
) -> dict[str, object]:
    """Build a backend Simulink model and validate its blocks exist."""
    normalized = validate_simulink_model_dict(model_dict)
    build_info = build_core_model(
        eng,
        {
            "name": normalized["name"],
            "blocks": normalized["blocks"],
            "connections": normalized["connections"],
        },
        output_dir=output_dir,
        open_after_build=open_after_build,
        run_simulation=False,
        preload_workspace_variables=normalized.get("workspace_variables", {}),
    )

    model_name = build_info["model_name"]
    for param_name, param_value in normalized["model_params"].items():
        eng.set_param(model_name, str(param_name), matlab_param_value(param_value), nargout=0)
    for variable_name, variable_value in normalized.get("workspace_variables", {}).items():
        _assign_workspace_value(eng, variable_name, variable_value)
    eng.set_param(model_name, "SimulationCommand", "update", nargout=0)
    eng.save_system(model_name, build_info["model_file"], nargout=0)

    for block_name in normalized["blocks"]:
        eng.get_param(f"{model_name}/{sanitize_block_name(block_name)}", "Handle", nargout=1)

    return {
        **build_info,
        "outputs": normalized["outputs"],
        "model_params": normalized["model_params"],
        "metadata": normalized["metadata"],
    }
