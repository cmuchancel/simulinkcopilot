"""Canonical dictionary representation for Simulink models."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

from simulink_v2.constants import CONSTANT_BLOCK, GAIN_BLOCK, SCOPE_BLOCK
from simulink_v2.utils import format_port, validate_library_path


class BlockSpec(TypedDict, total=False):
    type: str
    lib_path: str
    params: dict[str, Any]
    position: list[int]


class SimulinkModelDict(TypedDict):
    name: str
    blocks: dict[str, BlockSpec]
    connections: list[tuple[str, str, str, str]]


def validate_model_dict(model_dict: Mapping[str, Any]) -> SimulinkModelDict:
    """Normalize and validate the canonical Simulink model dictionary."""
    if not isinstance(model_dict, Mapping):
        raise TypeError("Model definitions must be dictionaries or dictionary-like mappings.")

    model_name = str(model_dict.get("name", "")).strip()
    if not model_name:
        raise ValueError("Model dictionaries require a non-empty 'name'.")

    blocks = model_dict.get("blocks")
    if not isinstance(blocks, Mapping) or not blocks:
        raise ValueError("Model dictionaries require a non-empty 'blocks' mapping.")

    normalized_blocks: dict[str, BlockSpec] = {}
    for block_name, raw_spec in blocks.items():
        if not isinstance(block_name, str) or not block_name.strip():
            raise ValueError(f"Invalid block name: {block_name!r}")
        if not isinstance(raw_spec, Mapping):
            raise TypeError(f"Block {block_name!r} must map to a dictionary of properties.")

        lib_path = validate_library_path(str(raw_spec.get("lib_path", "")))
        params = raw_spec.get("params", {})
        if not isinstance(params, Mapping):
            raise TypeError(f"Block {block_name!r} has non-dictionary params: {params!r}")

        block_spec: BlockSpec = {
            "type": str(raw_spec.get("type", block_name)),
            "lib_path": lib_path,
            "params": dict(params),
        }

        position = raw_spec.get("position")
        if position is not None:
            if not isinstance(position, (list, tuple)) or len(position) != 4:
                raise ValueError(f"Block {block_name!r} position must be a four-value list or tuple.")
            block_spec["position"] = [int(value) for value in position]

        normalized_blocks[block_name] = block_spec

    raw_connections = model_dict.get("connections", [])
    if not isinstance(raw_connections, list):
        raise TypeError("Model 'connections' must be a list of 4-tuples.")

    normalized_connections: list[tuple[str, str, str, str]] = []
    for connection in raw_connections:
        if not isinstance(connection, (list, tuple)) or len(connection) != 4:
            raise ValueError(f"Invalid connection entry: {connection!r}")
        src_block, src_port, dst_block, dst_port = connection
        if src_block not in normalized_blocks:
            raise ValueError(f"Connection references unknown source block {src_block!r}.")
        if dst_block not in normalized_blocks:
            raise ValueError(f"Connection references unknown destination block {dst_block!r}.")
        normalized_connections.append(
            (
                str(src_block),
                format_port(src_port),
                str(dst_block),
                format_port(dst_port),
            )
        )

    return {
        "name": model_name,
        "blocks": normalized_blocks,
        "connections": normalized_connections,
    }


def example_model(name: str = "example_model") -> SimulinkModelDict:
    """Return a minimal constant -> gain -> scope example model."""
    return validate_model_dict(
        {
            "name": name,
            "blocks": {
                "const1": {
                    "type": "Constant",
                    "lib_path": CONSTANT_BLOCK,
                    "params": {"Value": 1},
                },
                "gain1": {
                    "type": "Gain",
                    "lib_path": GAIN_BLOCK,
                    "params": {"Gain": 2},
                },
                "scope1": {
                    "type": "Scope",
                    "lib_path": SCOPE_BLOCK,
                    "params": {},
                },
            },
            "connections": [
                ("const1", "1", "gain1", "1"),
                ("gain1", "1", "scope1", "1"),
            ],
        }
    )
