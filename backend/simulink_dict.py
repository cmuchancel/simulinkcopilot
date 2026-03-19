"""Hierarchical Simulink model dictionaries for the readable backend."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

from simulink.utils import format_port, validate_library_path


ROOT_SYSTEM = "root"
SUBSYSTEM_BLOCK = "simulink/Ports & Subsystems/Subsystem"


class BlockSpec(TypedDict, total=False):
    type: str
    lib_path: str
    params: dict[str, Any]
    position: list[int]
    system: str
    name: str
    metadata: dict[str, Any]


class ConnectionSpec(TypedDict, total=False):
    system: str
    src_block: str
    src_port: str
    dst_block: str
    dst_port: str
    label: str
    metadata: dict[str, Any]


class OutputSpec(TypedDict):
    name: str
    block: str
    port: str


class BackendSimulinkModelDict(TypedDict, total=False):
    name: str
    blocks: dict[str, BlockSpec]
    connections: list[ConnectionSpec]
    outputs: list[OutputSpec]
    model_params: dict[str, Any]
    workspace_variables: dict[str, Any]
    metadata: dict[str, Any]


def _normalize_position(position: object, block_name: str) -> list[int] | None:
    if position is None:
        return None
    if not isinstance(position, (list, tuple)) or len(position) != 4:
        raise ValueError(f"Block {block_name!r} position must be a four-value list or tuple.")
    return [int(value) for value in position]


def _normalize_block(block_name: str, raw_spec: Mapping[str, Any]) -> BlockSpec:
    lib_path = validate_library_path(str(raw_spec.get("lib_path", "")))
    params = raw_spec.get("params", {})
    if not isinstance(params, Mapping):
        raise TypeError(f"Block {block_name!r} has non-dictionary params: {params!r}")
    metadata = raw_spec.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise TypeError(f"Block {block_name!r} metadata must be a mapping.")

    block_spec: BlockSpec = {
        "type": str(raw_spec.get("type", block_name)),
        "lib_path": lib_path,
        "params": dict(params),
        "system": str(raw_spec.get("system", ROOT_SYSTEM)).strip() or ROOT_SYSTEM,
        "name": str(raw_spec.get("name", block_name)).strip() or block_name,
        "metadata": dict(metadata),
    }
    position = _normalize_position(raw_spec.get("position"), block_name)
    if position is not None:
        block_spec["position"] = position
    return block_spec


def _normalize_connection(connection: object) -> ConnectionSpec:
    if isinstance(connection, Mapping):
        metadata = connection.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise TypeError(f"Invalid connection metadata: {metadata!r}")
        normalized: ConnectionSpec = {
            "system": str(connection.get("system", ROOT_SYSTEM)).strip() or ROOT_SYSTEM,
            "src_block": str(connection.get("src_block", "")).strip(),
            "src_port": format_port(connection.get("src_port", "")),
            "dst_block": str(connection.get("dst_block", "")).strip(),
            "dst_port": format_port(connection.get("dst_port", "")),
            "label": str(connection.get("label", "")),
            "metadata": dict(metadata),
        }
        if not normalized["src_block"] or not normalized["dst_block"]:
            raise ValueError(f"Invalid connection entry: {connection!r}")
        return normalized

    if not isinstance(connection, (list, tuple)) or len(connection) != 4:
        raise ValueError(f"Invalid connection entry: {connection!r}")
    src_block, src_port, dst_block, dst_port = connection
    return {
        "system": ROOT_SYSTEM,
        "src_block": str(src_block),
        "src_port": format_port(src_port),
        "dst_block": str(dst_block),
        "dst_port": format_port(dst_port),
        "label": "",
        "metadata": {},
    }


def _validate_system_tree(blocks: Mapping[str, BlockSpec]) -> None:
    for block_name, block_spec in blocks.items():
        system = block_spec["system"]
        if system == ROOT_SYSTEM:
            continue
        if system not in blocks:
            raise ValueError(f"Block {block_name!r} references unknown parent system {system!r}.")
        parent = blocks[system]
        if parent["lib_path"] != SUBSYSTEM_BLOCK:
            raise ValueError(f"Parent system {system!r} for block {block_name!r} is not a subsystem block.")


def _validate_connections(
    blocks: Mapping[str, BlockSpec],
    connections: list[ConnectionSpec],
) -> None:
    for connection in connections:
        system = connection["system"]
        if system != ROOT_SYSTEM:
            if system not in blocks:
                raise ValueError(f"Connection references unknown system {system!r}.")
            if blocks[system]["lib_path"] != SUBSYSTEM_BLOCK:
                raise ValueError(f"Connection system {system!r} is not a subsystem block.")

        src_block = connection["src_block"]
        dst_block = connection["dst_block"]
        if src_block not in blocks:
            raise ValueError(f"Connection references unknown source block {src_block!r}.")
        if dst_block not in blocks:
            raise ValueError(f"Connection references unknown destination block {dst_block!r}.")
        if blocks[src_block]["system"] != system:
            raise ValueError(
                f"Source block {src_block!r} does not belong to connection system {system!r}."
            )
        if blocks[dst_block]["system"] != system:
            raise ValueError(
                f"Destination block {dst_block!r} does not belong to connection system {system!r}."
            )


def validate_simulink_model_dict(model_dict: Mapping[str, Any]) -> BackendSimulinkModelDict:
    """Validate and normalize the extended hierarchical backend model dictionary."""
    if not isinstance(model_dict, Mapping):
        raise TypeError("Model definitions must be dictionaries or dictionary-like mappings.")

    model_name = str(model_dict.get("name", "")).strip()
    if not model_name:
        raise ValueError("Model dictionaries require a non-empty 'name'.")

    raw_blocks = model_dict.get("blocks")
    if not isinstance(raw_blocks, Mapping) or not raw_blocks:
        raise ValueError("Model dictionaries require a non-empty 'blocks' mapping.")

    normalized_blocks: dict[str, BlockSpec] = {}
    for block_name, raw_spec in raw_blocks.items():
        if not isinstance(block_name, str) or not block_name.strip():
            raise ValueError(f"Invalid block name: {block_name!r}")
        if not isinstance(raw_spec, Mapping):
            raise TypeError(f"Block {block_name!r} must map to a dictionary of properties.")
        normalized_blocks[block_name] = _normalize_block(block_name, raw_spec)

    _validate_system_tree(normalized_blocks)

    raw_connections = model_dict.get("connections", [])
    if not isinstance(raw_connections, list):
        raise TypeError("Model 'connections' must be a list.")
    normalized_connections = [_normalize_connection(entry) for entry in raw_connections]
    normalized_connections.sort(
        key=lambda entry: (
            entry["system"],
            entry["src_block"],
            entry["src_port"],
            entry["dst_block"],
            entry["dst_port"],
            entry["label"],
        )
    )
    _validate_connections(normalized_blocks, normalized_connections)

    outputs = model_dict.get("outputs", [])
    if not isinstance(outputs, list):
        raise TypeError("Backend model 'outputs' must be a list.")
    normalized_outputs: list[OutputSpec] = []
    for entry in outputs:
        if not isinstance(entry, Mapping):
            raise TypeError(f"Invalid output spec: {entry!r}")
        name = str(entry.get("name", "")).strip()
        block = str(entry.get("block", "")).strip()
        port = str(entry.get("port", "")).strip()
        if not name or not block or not port:
            raise ValueError(f"Invalid output spec: {entry!r}")
        if block not in normalized_blocks:
            raise ValueError(f"Output {name!r} references unknown block {block!r}.")
        normalized_outputs.append({"name": name, "block": block, "port": port})
    model_params = model_dict.get("model_params", {})
    if not isinstance(model_params, Mapping):
        raise TypeError("Backend model 'model_params' must be a mapping.")

    workspace_variables = model_dict.get("workspace_variables", {})
    if not isinstance(workspace_variables, Mapping):
        raise TypeError("Backend model 'workspace_variables' must be a mapping.")

    metadata = model_dict.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise TypeError("Backend model 'metadata' must be a mapping.")

    return {
        "name": model_name,
        "blocks": normalized_blocks,
        "connections": normalized_connections,
        "outputs": normalized_outputs,
        "model_params": dict(model_params),
        "workspace_variables": dict(workspace_variables),
        "metadata": dict(metadata),
    }
