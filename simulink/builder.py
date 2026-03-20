"""Build Simulink models from canonical Python dictionaries."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matlab

from ir.simulink_dict import validate_model_dict
from repo_paths import GENERATED_MODELS_ROOT
from simulink.constants import (
    DEFAULT_BLOCK_POSITION,
    DEFAULT_HORIZONTAL_SPACING,
    DEFAULT_VERTICAL_SPACING,
)
from simulink.utils import (
    ensure_output_dir,
    format_port,
    format_position,
    matlab_param_value,
    sanitize_block_name,
)

LOGGER = logging.getLogger(__name__)


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


def _default_position(index: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = DEFAULT_BLOCK_POSITION
    row = index % 4
    column = index // 4
    x_offset = column * DEFAULT_HORIZONTAL_SPACING
    y_offset = row * DEFAULT_VERTICAL_SPACING
    return (
        left + x_offset,
        top + y_offset,
        right + x_offset,
        bottom + y_offset,
    )


def _close_model_if_loaded(eng, model_name: str) -> None:
    eng.eval(
        f"if bdIsLoaded('{model_name}'), close_system('{model_name}', 0); end",
        nargout=0,
    )


def build_model(
    eng,
    model_dict: dict[str, Any],
    output_dir: str | Path | None = None,
    open_after_build: bool = False,
    run_simulation: bool = False,
    preload_workspace_variables: dict[str, object] | None = None,
) -> dict[str, str]:
    """Create, connect, save, and optionally simulate a Simulink model."""
    normalized_model = validate_model_dict(model_dict)
    model_name = sanitize_block_name(normalized_model["name"])
    output_root = ensure_output_dir(output_dir or GENERATED_MODELS_ROOT)
    model_file = output_root / f"{model_name}.slx"

    LOGGER.info("Building Simulink model %s", model_name)
    eng.load_system("simulink", nargout=0)
    _close_model_if_loaded(eng, model_name)
    eng.new_system(model_name, nargout=0)
    for variable_name, variable_value in (preload_workspace_variables or {}).items():
        _assign_workspace_value(eng, variable_name, variable_value)

    for index, (block_name, block_spec) in enumerate(normalized_model["blocks"].items()):
        sanitized_name = sanitize_block_name(block_name)
        block_path = f"{model_name}/{sanitized_name}"
        eng.add_block(block_spec["lib_path"], block_path, nargout=0)

        position = block_spec.get("position", list(_default_position(index)))
        eng.set_param(block_path, "Position", format_position(position), nargout=0)

        for param_name, param_value in block_spec.get("params", {}).items():
            eng.set_param(block_path, str(param_name), matlab_param_value(param_value), nargout=0)

    for src_block, src_port, dst_block, dst_port in normalized_model["connections"]:
        eng.add_line(
            model_name,
            f"{sanitize_block_name(src_block)}/{format_port(src_port)}",
            f"{sanitize_block_name(dst_block)}/{format_port(dst_port)}",
            "autorouting",
            "on",
            nargout=0,
        )

    eng.set_param(model_name, "SimulationCommand", "update", nargout=0)
    if open_after_build:
        eng.open_system(model_name, nargout=0)
    eng.save_system(model_name, str(model_file), "OverwriteIfChangedOnDisk", "on", nargout=0)

    if run_simulation:
        eng.sim(model_name, nargout=0)

    return {
        "model_name": model_name,
        "model_file": str(model_file),
    }
