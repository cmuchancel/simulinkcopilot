"""MATLAB-backed rendering helpers for readable Simulink model dictionaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.builder import _build_block_path_names, build_simulink_model
from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict, validate_simulink_model_dict


@dataclass(frozen=True)
class MatlabRenderedModel:
    model_name: str
    model_file: str
    renders: dict[str, str]


def _matlab_string_literal(value: str) -> str:
    return value.replace("'", "''")


def _full_block_path(
    model_name: str,
    block_id: str,
    blocks: dict[str, dict[str, object]],
    block_path_names: dict[str, str],
) -> str:
    ancestors: list[str] = []
    current = block_id
    while True:
        ancestors.append(block_path_names[current])
        block_spec = blocks[current]
        parent = str(block_spec["system"])
        if parent == ROOT_SYSTEM:
            break
        current = parent
    ancestors.reverse()
    return "/".join([model_name, *ancestors])


def _system_path(
    model_name: str,
    system: str,
    blocks: dict[str, dict[str, object]],
    block_path_names: dict[str, str],
) -> str:
    if system == ROOT_SYSTEM:
        return model_name
    return _full_block_path(model_name, system, blocks, block_path_names)


def export_simulink_system_image(
    eng,
    *,
    system_path: str,
    output_path: str | Path,
) -> str:
    """Export a real Simulink canvas image for a model or subsystem."""
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    escaped_system = _matlab_string_literal(system_path)
    escaped_output = _matlab_string_literal(str(output))
    eng.open_system(system_path, nargout=0)
    eng.eval("drawnow;", nargout=0)
    eng.eval(f"set_param('{escaped_system}', 'ZoomFactor', 'FitSystem');", nargout=0)
    eng.eval("drawnow;", nargout=0)
    eng.eval(f"print('-s{escaped_system}', '-dpng', '-r150', '{escaped_output}')", nargout=0)
    return str(output)


def render_backend_model_with_matlab(
    eng,
    model: BackendSimulinkModelDict | dict[str, object],
    *,
    output_dir: str | Path,
    systems: list[str] | None = None,
    open_after_build: bool = False,
    close_after_render: bool = True,
) -> MatlabRenderedModel:
    """Build a backend model in Simulink and export real PNG renders."""
    normalized = validate_simulink_model_dict(model)
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    build_info = build_simulink_model(
        eng,
        normalized,
        output_dir=output_root,
        open_after_build=open_after_build,
    )
    model_name = str(build_info["model_name"])
    blocks = normalized["blocks"]
    block_path_names = _build_block_path_names(blocks)
    requested_systems = systems or [
        ROOT_SYSTEM,
        *sorted(
            block_id
            for block_id, block_spec in blocks.items()
            if block_spec["type"] == "Subsystem" and block_spec["system"] == ROOT_SYSTEM
        ),
    ]
    renders: dict[str, str] = {}
    try:
        for system in requested_systems:
            system_path = _system_path(model_name, system, blocks, block_path_names)
            renders[system] = export_simulink_system_image(
                eng,
                system_path=system_path,
                output_path=output_root / f"{system}.png",
            )
    finally:
        if close_after_render:
            try:
                eng.close_system(model_name, 0, nargout=0)
            except Exception:
                pass

    return MatlabRenderedModel(
        model_name=model_name,
        model_file=str(build_info["model_file"]),
        renders=renders,
    )
