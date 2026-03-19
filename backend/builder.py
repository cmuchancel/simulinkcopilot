"""MATLAB-backed builder for hierarchical readable Simulink model dictionaries."""

from __future__ import annotations

from pathlib import Path

import matlab

from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict, validate_simulink_model_dict
from simulink.utils import ensure_output_dir, format_position, matlab_param_value, sanitize_block_name


def _assign_workspace_value(eng, name: str, value: object) -> None:
    if isinstance(value, list) and value and all(isinstance(row, list) for row in value):
        eng.workspace[name] = matlab.double(value)
    else:
        eng.workspace[name] = value
    eng.eval(f"assignin('base', '{name}', {name});", nargout=0)


def _close_model_if_loaded(eng, model_name: str) -> None:
    eng.eval(
        f"if bdIsLoaded('{model_name}'), close_system('{model_name}', 0); end",
        nargout=0,
    )


def _block_depth(block_id: str, blocks: dict[str, dict[str, object]]) -> int:
    depth = 0
    current = blocks[block_id]["system"]
    while current != ROOT_SYSTEM:
        depth += 1
        current = blocks[current]["system"]
    return depth


def _full_block_path(model_name: str, block_id: str, blocks: dict[str, dict[str, object]]) -> str:
    ancestors: list[str] = []
    current = block_id
    while True:
        block_spec = blocks[current]
        ancestors.append(sanitize_block_name(str(block_spec["name"])))
        parent = block_spec["system"]
        if parent == ROOT_SYSTEM:
            break
        current = str(parent)
    ancestors.reverse()
    return "/".join([model_name, *ancestors])


def _system_path(model_name: str, system: str, blocks: dict[str, dict[str, object]]) -> str:
    if system == ROOT_SYSTEM:
        return model_name
    return _full_block_path(model_name, system, blocks)


def _port_sort_key(block_spec: dict[str, object]) -> tuple[int, int]:
    block_type = str(block_spec["type"])
    if block_type == "Inport":
        return (0, int(block_spec.get("params", {}).get("Port", 0)))
    if block_type == "Outport":
        return (1, int(block_spec.get("params", {}).get("Port", 0)))
    return (2, 0)


def build_simulink_model(
    eng,
    model_dict: BackendSimulinkModelDict | dict[str, object],
    *,
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
) -> dict[str, object]:
    """Build a hierarchical backend model and validate that all blocks exist."""
    normalized = validate_simulink_model_dict(model_dict)
    model_name = sanitize_block_name(normalized["name"])
    output_root = ensure_output_dir(output_dir or Path.cwd() / "generated_models")
    model_file = output_root / f"{model_name}.slx"

    eng.load_system("simulink", nargout=0)
    _close_model_if_loaded(eng, model_name)
    eng.new_system(model_name, nargout=0)

    for variable_name, variable_value in normalized.get("workspace_variables", {}).items():
        _assign_workspace_value(eng, variable_name, variable_value)

    blocks = normalized["blocks"]
    build_order = sorted(
        blocks,
        key=lambda block_id: (
            _block_depth(block_id, blocks),
            _system_path(model_name, blocks[block_id]["system"], blocks),
            _port_sort_key(blocks[block_id]),
            sanitize_block_name(str(blocks[block_id]["name"])),
            block_id,
        ),
    )

    for block_id in build_order:
        block_spec = blocks[block_id]
        block_path = _full_block_path(model_name, block_id, blocks)
        eng.add_block(block_spec["lib_path"], block_path, nargout=0)
        position = block_spec.get("position")
        if position is not None:
            eng.set_param(block_path, "Position", format_position(position), nargout=0)
        for param_name, param_value in block_spec.get("params", {}).items():
            eng.set_param(block_path, str(param_name), matlab_param_value(param_value), nargout=0)

    # Materialize subsystem external port ordering before root-level wiring.
    eng.set_param(model_name, "SimulationCommand", "update", nargout=0)

    for connection in normalized["connections"]:
        system_path = _system_path(model_name, connection["system"], blocks)
        src_local = sanitize_block_name(str(blocks[connection["src_block"]]["name"]))
        dst_local = sanitize_block_name(str(blocks[connection["dst_block"]]["name"]))
        line_handle = eng.add_line(
            system_path,
            f"{src_local}/{connection['src_port']}",
            f"{dst_local}/{connection['dst_port']}",
            "autorouting",
            "on",
            nargout=1,
        )
        if connection.get("label"):
            eng.set_param(line_handle, "Name", str(connection["label"]), nargout=0)

    for param_name, param_value in normalized["model_params"].items():
        eng.set_param(model_name, str(param_name), matlab_param_value(param_value), nargout=0)
    for variable_name, variable_value in normalized.get("workspace_variables", {}).items():
        _assign_workspace_value(eng, variable_name, variable_value)

    eng.set_param(model_name, "SimulationCommand", "update", nargout=0)
    if open_after_build:
        eng.open_system(model_name, nargout=0)
    eng.save_system(model_name, str(model_file), "OverwriteIfChangedOnDisk", "on", nargout=0)

    for block_id in build_order:
        eng.get_param(_full_block_path(model_name, block_id, blocks), "Handle", nargout=1)

    return {
        "model_name": model_name,
        "model_file": str(model_file),
        "outputs": normalized["outputs"],
        "model_params": normalized["model_params"],
        "metadata": normalized["metadata"],
    }
