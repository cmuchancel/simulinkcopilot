"""Deterministic visual layout for hierarchical Simulink model dictionaries."""

from __future__ import annotations

from copy import deepcopy

from backend_v2.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict
from backend_v2.traceability import state_order


ROOT_SOURCE_X = 40
ROOT_SHARED_X = 240
ROOT_SUBSYSTEM_X = 560
ROOT_OUTPORT_X = 860
SUBSYSTEM_INPORT_X = 40
SUBSYSTEM_COMPUTE_X = 240
SUBSYSTEM_INTEGRATOR_X = 620
SUBSYSTEM_OUTPORT_X = 860
DEFAULT_BLOCK_WIDTH = 110
DEFAULT_BLOCK_HEIGHT = 40
SUBSYSTEM_BLOCK_WIDTH = 220
ROOT_Y_SPACING = 90
SUBSYSTEM_Y_SPACING = 80
LAYER_X_SPACING = 150


def _block_height(block_spec: dict[str, object]) -> int:
    if block_spec["type"] == "Subsystem":
        return 140
    return DEFAULT_BLOCK_HEIGHT


def _position(x: int, y: int, width: int = DEFAULT_BLOCK_WIDTH, height: int = DEFAULT_BLOCK_HEIGHT) -> list[int]:
    return [x, y, x + width, y + height]


def _sort_blocks(block_ids: list[str], blocks: dict[str, dict[str, object]]) -> list[str]:
    return sorted(block_ids, key=lambda block_id: (str(blocks[block_id].get("name", block_id)), block_id))


def _assign_root_layout(model: BackendSimulinkModelDict) -> None:
    blocks = model["blocks"]
    root_blocks = [block_id for block_id, spec in blocks.items() if spec["system"] == ROOT_SYSTEM]
    sources = _sort_blocks(
        [block_id for block_id in root_blocks if blocks[block_id]["metadata"].get("layout_role") == "source"],
        blocks,
    )
    shared = _sort_blocks(
        [block_id for block_id in root_blocks if blocks[block_id]["metadata"].get("layout_role") == "shared"],
        blocks,
    )
    subsystems = _sort_blocks(
        [block_id for block_id in root_blocks if blocks[block_id]["type"] == "Subsystem"],
        blocks,
    )
    outputs = _sort_blocks(
        [block_id for block_id in root_blocks if blocks[block_id]["metadata"].get("layout_role") == "output"],
        blocks,
    )

    for index, block_id in enumerate(sources):
        blocks[block_id]["position"] = _position(ROOT_SOURCE_X, 40 + index * ROOT_Y_SPACING)

    shared_by_layer: dict[int, list[str]] = {}
    for block_id in shared:
        layer = int(blocks[block_id]["metadata"].get("layer_hint", 0))
        shared_by_layer.setdefault(layer, []).append(block_id)
    max_shared_layer = -1
    for layer in sorted(shared_by_layer):
        max_shared_layer = max(max_shared_layer, layer)
        for index, block_id in enumerate(_sort_blocks(shared_by_layer[layer], blocks)):
            blocks[block_id]["position"] = _position(
                ROOT_SHARED_X + layer * LAYER_X_SPACING,
                40 + index * ROOT_Y_SPACING,
            )

    subsystem_x = ROOT_SUBSYSTEM_X + max(0, max_shared_layer) * 40
    for index, block_id in enumerate(subsystems):
        port_count = max(
            int(blocks[block_id]["metadata"].get("inport_count", 1)),
            int(blocks[block_id]["metadata"].get("outport_count", 1)),
            1,
        )
        height = max(140, 40 + port_count * 40)
        blocks[block_id]["position"] = _position(
            subsystem_x,
            40 + index * (height + 40),
            width=SUBSYSTEM_BLOCK_WIDTH,
            height=height,
        )

    for index, block_id in enumerate(outputs):
        blocks[block_id]["position"] = _position(ROOT_OUTPORT_X, 60 + index * ROOT_Y_SPACING)


def _assign_subsystem_layout(model: BackendSimulinkModelDict, subsystem_id: str) -> None:
    blocks = model["blocks"]
    local_blocks = [block_id for block_id, spec in blocks.items() if spec["system"] == subsystem_id]
    inports = _sort_blocks(
        [block_id for block_id in local_blocks if blocks[block_id]["type"] == "Inport"],
        blocks,
    )
    compute = _sort_blocks(
        [
            block_id
            for block_id in local_blocks
            if blocks[block_id]["metadata"].get("layout_role") == "compute"
        ],
        blocks,
    )
    integrators = sorted(
        [block_id for block_id in local_blocks if blocks[block_id]["type"] == "Integrator"],
        key=lambda block_id: (
            -int(blocks[block_id]["metadata"].get("state_order", 0)),
            str(blocks[block_id].get("name", block_id)),
        ),
    )
    outports = _sort_blocks(
        [block_id for block_id in local_blocks if blocks[block_id]["type"] == "Outport"],
        blocks,
    )

    for index, block_id in enumerate(inports):
        blocks[block_id]["position"] = _position(SUBSYSTEM_INPORT_X, 40 + index * SUBSYSTEM_Y_SPACING)

    compute_by_layer: dict[int, list[str]] = {}
    for block_id in compute:
        layer = int(blocks[block_id]["metadata"].get("layer_hint", 0))
        compute_by_layer.setdefault(layer, []).append(block_id)
    max_compute_x = SUBSYSTEM_COMPUTE_X
    for layer in sorted(compute_by_layer):
        x = SUBSYSTEM_COMPUTE_X + layer * LAYER_X_SPACING
        max_compute_x = max(max_compute_x, x)
        for index, block_id in enumerate(_sort_blocks(compute_by_layer[layer], blocks)):
            blocks[block_id]["position"] = _position(x, 40 + index * SUBSYSTEM_Y_SPACING)

    integrator_x = max_compute_x + 180 if compute else SUBSYSTEM_INTEGRATOR_X
    for index, block_id in enumerate(integrators):
        blocks[block_id]["position"] = _position(integrator_x, 40 + index * SUBSYSTEM_Y_SPACING)

    outport_x = integrator_x + 180
    for index, block_id in enumerate(outports):
        blocks[block_id]["position"] = _position(outport_x, 40 + index * SUBSYSTEM_Y_SPACING)


def apply_deterministic_layout(model: BackendSimulinkModelDict) -> BackendSimulinkModelDict:
    """Assign deterministic positions to every block in a hierarchical model."""
    laid_out = deepcopy(model)
    _assign_root_layout(laid_out)
    subsystem_ids = [
        block_id
        for block_id, spec in laid_out["blocks"].items()
        if spec["system"] == ROOT_SYSTEM and spec["type"] == "Subsystem"
    ]
    for subsystem_id in sorted(subsystem_ids, key=lambda block_id: str(laid_out["blocks"][block_id]["name"])):
        _assign_subsystem_layout(laid_out, subsystem_id)
    return laid_out


def annotate_integrator_orders(model: BackendSimulinkModelDict) -> None:
    """Attach derivative-order hints to integrators for vertical chain layout."""
    for block_spec in model["blocks"].values():
        if block_spec["type"] != "Integrator":
            continue
        metadata = block_spec.setdefault("metadata", {})
        state = str(metadata.get("state", ""))
        metadata["state_order"] = state_order(state) if state else 0
