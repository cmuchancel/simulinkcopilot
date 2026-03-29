"""MATLAB-backed builder for hierarchical readable Simulink model dictionaries."""

from __future__ import annotations

from pathlib import Path

from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict, validate_simulink_model_dict
from repo_paths import GENERATED_MODELS_ROOT
from simulink.engine import import_matlab_engine
from simulink.utils import ensure_output_dir, format_position, matlab_param_value, sanitize_block_name


def _assign_workspace_value(eng, name: str, value: object) -> None:
    matlab = import_matlab_engine()
    if isinstance(value, list) and value and all(isinstance(row, list) for row in value):
        eng.workspace[name] = matlab.double(value)
    else:
        eng.workspace[name] = value
    eng.eval(f"assignin('base', '{name}', {name});", nargout=0)


def _configure_matlab_function_block(eng, block_path: str, script: str) -> None:
    eng.workspace["simucopilot_block_path_tmp"] = str(block_path)
    eng.workspace["simucopilot_block_script_tmp"] = str(script)
    eng.eval(
        "rt = sfroot; "
        "ch = rt.find('-isa', 'Stateflow.EMChart', 'Path', simucopilot_block_path_tmp); "
        "if isempty(ch), error('Could not locate MATLAB Function chart for block %s.', simucopilot_block_path_tmp); end; "
        "ch(1).Script = simucopilot_block_script_tmp;",
        nargout=0,
    )


def _configure_special_block(eng, block_path: str, block_spec: dict[str, object]) -> None:
    metadata = block_spec.get("metadata", {})
    if not isinstance(metadata, dict):
        return
    if str(block_spec.get("type", "")) == "MATLABFunction":
        script = metadata.get("matlab_function_script")
        if not isinstance(script, str) or not script.strip():
            raise ValueError(f"MATLABFunction block at {block_path!r} requires metadata.matlab_function_script.")
        _configure_matlab_function_block(eng, block_path, script)


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


def _build_block_path_names(blocks: dict[str, dict[str, object]]) -> dict[str, str]:
    by_system: dict[str, list[str]] = {}
    for block_id, block_spec in blocks.items():
        by_system.setdefault(str(block_spec["system"]), []).append(block_id)

    resolved: dict[str, str] = {}
    for system, block_ids in by_system.items():
        seen_counts: dict[str, int] = {}
        for block_id in sorted(
            block_ids,
            key=lambda candidate: (
                sanitize_block_name(str(blocks[candidate]["name"])),
                candidate,
            ),
        ):
            base_name = sanitize_block_name(str(blocks[block_id]["name"]))
            count = seen_counts.get(base_name, 0)
            if count == 0:
                resolved[block_id] = base_name
            else:
                resolved[block_id] = f"{base_name}__{count + 1}"
            seen_counts[base_name] = count + 1
    return resolved


def _full_block_path(
    model_name: str,
    block_id: str,
    blocks: dict[str, dict[str, object]],
    block_path_names: dict[str, str] | None = None,
) -> str:
    if block_path_names is None:
        block_path_names = _build_block_path_names(blocks)
    ancestors: list[str] = []
    current = block_id
    while True:
        ancestors.append(block_path_names[current])
        block_spec = blocks[current]
        parent = block_spec["system"]
        if parent == ROOT_SYSTEM:
            break
        current = str(parent)
    ancestors.reverse()
    return "/".join([model_name, *ancestors])


def _system_path(
    model_name: str,
    system: str,
    blocks: dict[str, dict[str, object]],
    block_path_names: dict[str, str] | None = None,
) -> str:
    if system == ROOT_SYSTEM:
        return model_name
    return _full_block_path(model_name, system, blocks, block_path_names)


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
    output_root = ensure_output_dir(output_dir or GENERATED_MODELS_ROOT)
    model_file = output_root / f"{model_name}.slx"

    eng.load_system("simulink", nargout=0)
    _close_model_if_loaded(eng, model_name)
    eng.new_system(model_name, nargout=0)

    for variable_name, variable_value in normalized.get("workspace_variables", {}).items():
        _assign_workspace_value(eng, variable_name, variable_value)

    blocks = normalized["blocks"]
    block_path_names = _build_block_path_names(blocks)
    build_order = sorted(
        blocks,
        key=lambda block_id: (
            _block_depth(block_id, blocks),
            _system_path(model_name, blocks[block_id]["system"], blocks, block_path_names),
            _port_sort_key(blocks[block_id]),
            sanitize_block_name(str(blocks[block_id]["name"])),
            block_id,
        ),
    )

    for block_id in build_order:
        block_spec = blocks[block_id]
        block_path = _full_block_path(model_name, block_id, blocks, block_path_names)
        eng.add_block(block_spec["lib_path"], block_path, nargout=0)
        position = block_spec.get("position")
        if position is not None:
            eng.set_param(block_path, "Position", format_position(position), nargout=0)
        for param_name, param_value in block_spec.get("params", {}).items():
            eng.set_param(block_path, str(param_name), matlab_param_value(param_value), nargout=0)
        _configure_special_block(eng, block_path, block_spec)

    # Materialize subsystem external port ordering before root-level wiring.
    eng.set_param(model_name, "SimulationCommand", "update", nargout=0)

    for connection in normalized["connections"]:
        system_path = _system_path(model_name, connection["system"], blocks, block_path_names)
        src_local = block_path_names[str(connection["src_block"])]
        dst_local = block_path_names[str(connection["dst_block"])]
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
        eng.get_param(_full_block_path(model_name, block_id, blocks, block_path_names), "Handle", nargout=1)

    return {
        "model_name": model_name,
        "model_file": str(model_file),
        "outputs": normalized["outputs"],
        "model_params": normalized["model_params"],
        "metadata": normalized["metadata"],
    }
