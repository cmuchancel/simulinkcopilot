"""Backend-specific Simulink model dictionary definitions."""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

from ir.simulink_dict import validate_model_dict as validate_core_model_dict


class OutputSpec(TypedDict):
    name: str
    block: str
    port: str


class BackendSimulinkModelDict(TypedDict, total=False):
    name: str
    blocks: dict[str, dict[str, Any]]
    connections: list[tuple[str, str, str, str]]
    outputs: list[OutputSpec]
    model_params: dict[str, Any]
    workspace_variables: dict[str, Any]
    metadata: dict[str, Any]


def validate_simulink_model_dict(model_dict: Mapping[str, Any]) -> BackendSimulinkModelDict:
    """Validate the extended backend model dictionary."""
    core = validate_core_model_dict(
        {
            "name": model_dict.get("name"),
            "blocks": model_dict.get("blocks"),
            "connections": model_dict.get("connections"),
        }
    )

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
        if block not in core["blocks"]:
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
        **core,
        "outputs": normalized_outputs,
        "model_params": dict(model_params),
        "workspace_variables": dict(workspace_variables),
        "metadata": dict(metadata),
    }
