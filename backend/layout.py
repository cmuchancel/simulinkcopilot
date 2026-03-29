"""Deterministic visual layout for hierarchical Simulink model dictionaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from itertools import combinations
from math import ceil

from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict
from backend.traceability import state_order


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
MIN_COLUMN_GAP = 90
MIN_ROW_GAP = 30
PORT_ROW_GAP = 40
TEXT_PADDING_X = 28
TEXT_PADDING_Y = 16
TRACE_CHAR_WIDTH = 7
TRACE_LINE_HEIGHT = 18
TRACE_WRAP_WIDTH = 28
MIN_BLOCK_CLEARANCE_TARGET = 24
MIN_LABEL_BLOCK_CLEARANCE_TARGET = 6
MIN_LABEL_LABEL_CLEARANCE_TARGET = 12
MAX_LAYOUT_REPAIR_ITERATIONS = 6
DEFAULT_REFINEMENT_PASSES = 4


Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class LayoutProfile:
    root_source_x: int = ROOT_SOURCE_X
    root_shared_x: int = ROOT_SHARED_X
    root_subsystem_x: int = ROOT_SUBSYSTEM_X
    root_outport_x: int = ROOT_OUTPORT_X
    subsystem_inport_x: int = SUBSYSTEM_INPORT_X
    subsystem_compute_x: int = SUBSYSTEM_COMPUTE_X
    subsystem_integrator_x: int = SUBSYSTEM_INTEGRATOR_X
    subsystem_outport_x: int = SUBSYSTEM_OUTPORT_X
    default_block_width: int = DEFAULT_BLOCK_WIDTH
    default_block_height: int = DEFAULT_BLOCK_HEIGHT
    subsystem_block_width: int = SUBSYSTEM_BLOCK_WIDTH
    root_y_spacing: int = ROOT_Y_SPACING
    subsystem_y_spacing: int = SUBSYSTEM_Y_SPACING
    layer_x_spacing: int = LAYER_X_SPACING
    min_column_gap: int = MIN_COLUMN_GAP
    min_row_gap: int = MIN_ROW_GAP
    port_row_gap: int = PORT_ROW_GAP
    text_padding_x: int = TEXT_PADDING_X
    text_padding_y: int = TEXT_PADDING_Y
    trace_char_width: int = TRACE_CHAR_WIDTH
    trace_line_height: int = TRACE_LINE_HEIGHT
    trace_wrap_width: int = TRACE_WRAP_WIDTH
    horizontal_scale: float = 1.0
    vertical_scale: float = 1.0
    refinement_passes: int = DEFAULT_REFINEMENT_PASSES

    def scaled_column_gap(self, suggested_gap: int) -> int:
        return max(
            int(ceil(self.min_column_gap * self.horizontal_scale)),
            int(ceil(suggested_gap * self.horizontal_scale)),
        )

    def scaled_row_gap(self) -> int:
        return max(0, int(ceil(self.min_row_gap * self.vertical_scale)))

    def scaled_port_row_gap(self) -> int:
        return max(0, int(ceil(self.port_row_gap * self.vertical_scale)))


@dataclass(frozen=True)
class LayoutQualityReport:
    block_overlap_count: int
    label_block_overlap_count: int
    label_label_overlap_count: int
    min_block_clearance: int | None
    min_label_block_clearance: int | None
    min_label_label_clearance: int | None
    iterations: int
    profile: LayoutProfile

    @property
    def passes(self) -> bool:
        return (
            self.block_overlap_count == 0
            and self.label_block_overlap_count == 0
            and self.label_label_overlap_count == 0
            and (self.min_block_clearance is None or self.min_block_clearance >= MIN_BLOCK_CLEARANCE_TARGET)
            and (
                self.min_label_block_clearance is None
                or self.min_label_block_clearance >= MIN_LABEL_BLOCK_CLEARANCE_TARGET
            )
            and (
                self.min_label_label_clearance is None
                or self.min_label_label_clearance >= MIN_LABEL_LABEL_CLEARANCE_TARGET
            )
        )

    @property
    def score(self) -> float:
        penalty = 0.0
        penalty += self.block_overlap_count * 40.0
        penalty += self.label_block_overlap_count * 18.0
        penalty += self.label_label_overlap_count * 10.0
        penalty += max(0, MIN_BLOCK_CLEARANCE_TARGET - (self.min_block_clearance or MIN_BLOCK_CLEARANCE_TARGET))
        penalty += max(
            0,
            MIN_LABEL_BLOCK_CLEARANCE_TARGET - (self.min_label_block_clearance or MIN_LABEL_BLOCK_CLEARANCE_TARGET),
        )
        penalty += max(
            0,
            MIN_LABEL_LABEL_CLEARANCE_TARGET - (self.min_label_label_clearance or MIN_LABEL_LABEL_CLEARANCE_TARGET),
        )
        return max(0.0, 100.0 - penalty)

    def to_metadata(self) -> dict[str, object]:
        return {
            "passes": self.passes,
            "score": round(self.score, 2),
            "iterations": self.iterations,
            "block_overlap_count": self.block_overlap_count,
            "label_block_overlap_count": self.label_block_overlap_count,
            "label_label_overlap_count": self.label_label_overlap_count,
            "min_block_clearance": self.min_block_clearance,
            "min_label_block_clearance": self.min_label_block_clearance,
            "min_label_label_clearance": self.min_label_label_clearance,
            "profile": {
                "horizontal_scale": self.profile.horizontal_scale,
                "vertical_scale": self.profile.vertical_scale,
                "min_column_gap": self.profile.min_column_gap,
                "min_row_gap": self.profile.min_row_gap,
                "port_row_gap": self.profile.port_row_gap,
            },
        }


def _block_height(block_spec: dict[str, object], profile: LayoutProfile) -> int:
    visible_lines = _estimated_text_lines(_block_visible_text(block_spec), profile)
    desired_height = max(
        profile.default_block_height,
        visible_lines * profile.trace_line_height + profile.text_padding_y,
    )
    if block_spec["type"] == "Subsystem":
        return max(140, desired_height)
    return desired_height


def _block_width(block_spec: dict[str, object], profile: LayoutProfile) -> int:
    base_width = profile.subsystem_block_width if block_spec["type"] == "Subsystem" else profile.default_block_width
    text_width = _estimated_text_width(_block_visible_text(block_spec), profile) + profile.text_padding_x
    return max(base_width, text_width)


def _block_visible_text(block_spec: dict[str, object]) -> str:
    metadata = block_spec.get("metadata", {})
    if isinstance(metadata, dict):
        trace_expression = str(metadata.get("trace_expression", "")).strip()
    else:
        trace_expression = ""
    name = str(block_spec.get("name", "")).strip()
    return max((name, trace_expression), key=len, default="")


def _estimated_text_width(text: str, profile: LayoutProfile) -> int:
    if not text:
        return 0
    longest_line = max((len(line) for line in str(text).splitlines()), default=0)
    return longest_line * profile.trace_char_width


def _estimated_text_lines(text: str, profile: LayoutProfile) -> int:
    stripped = str(text).strip()
    if not stripped:
        return 1
    explicit_lines = stripped.splitlines()
    wrapped_lines = [
        max(1, ceil(len(line) / profile.trace_wrap_width))
        for line in explicit_lines
    ]
    return max(sum(wrapped_lines), 1)


def _connection_label_width(connection: dict[str, object], profile: LayoutProfile) -> int:
    return _estimated_text_width(str(connection.get("label", "")).strip(), profile)


def _connection_label_lines(connection: dict[str, object], profile: LayoutProfile) -> int:
    label = str(connection.get("label", "")).strip()
    return _estimated_text_lines(label, profile) if label else 0


def _column_label_width(
    model: BackendSimulinkModelDict,
    *,
    profile: LayoutProfile,
    system: str,
    src_block_ids: list[str],
) -> int:
    src_block_set = set(src_block_ids)
    widths = [
        _connection_label_width(connection, profile)
        for connection in model["connections"]
        if connection["system"] == system and connection["src_block"] in src_block_set and connection["label"]
    ]
    return max(widths, default=0)


def _block_label_line_budget(
    model: BackendSimulinkModelDict,
    *,
    profile: LayoutProfile,
    system: str,
    block_id: str,
) -> int:
    budgets = [
        _connection_label_lines(connection, profile)
        for connection in model["connections"]
        if connection["system"] == system
        and (connection["src_block"] == block_id or connection["dst_block"] == block_id)
        and connection["label"]
    ]
    return max(budgets, default=0)


def _column_x_after(
    model: BackendSimulinkModelDict,
    blocks: dict[str, dict[str, object]],
    *,
    profile: LayoutProfile,
    system: str,
    column_block_ids: list[str],
    start_x: int,
) -> int:
    if not column_block_ids:
        return start_x
    max_width = max(_block_width(blocks[block_id], profile) for block_id in column_block_ids)
    label_width = _column_label_width(model, profile=profile, system=system, src_block_ids=column_block_ids)
    return start_x + max_width + profile.scaled_column_gap(label_width + profile.text_padding_x)


def _stack_column(
    model: BackendSimulinkModelDict,
    blocks: dict[str, dict[str, object]],
    *,
    profile: LayoutProfile,
    system: str,
    block_ids: list[str],
    x: int,
    base_y: int,
) -> None:
    y = base_y
    previous_block_id: str | None = None
    for block_id in block_ids:
        if previous_block_id is not None:
            previous_height = _block_height(blocks[previous_block_id], profile)
            line_budget = max(
                _block_label_line_budget(model, profile=profile, system=system, block_id=previous_block_id),
                _block_label_line_budget(model, profile=profile, system=system, block_id=block_id),
            )
            y += previous_height + profile.scaled_row_gap() + max(0, line_budget - 1) * profile.trace_line_height
        width = _block_width(blocks[block_id], profile)
        height = _block_height(blocks[block_id], profile)
        blocks[block_id]["position"] = _position(x, y, width=width, height=height)
        previous_block_id = block_id


def _position(x: int, y: int, width: int = DEFAULT_BLOCK_WIDTH, height: int = DEFAULT_BLOCK_HEIGHT) -> list[int]:
    return [x, y, x + width, y + height]


def _center_y(position: list[int]) -> float:
    return (int(position[1]) + int(position[3])) / 2.0


def _sort_blocks(block_ids: list[str], blocks: dict[str, dict[str, object]]) -> list[str]:
    return sorted(block_ids, key=lambda block_id: (str(blocks[block_id].get("name", block_id)), block_id))


def _assign_root_layout(model: BackendSimulinkModelDict, profile: LayoutProfile) -> None:
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

    _stack_column(model, blocks, profile=profile, system=ROOT_SYSTEM, block_ids=sources, x=profile.root_source_x, base_y=40)

    shared_by_layer: dict[int, list[str]] = {}
    for block_id in shared:
        layer = int(blocks[block_id]["metadata"].get("layer_hint", 0))
        shared_by_layer.setdefault(layer, []).append(block_id)
    next_x = max(
        profile.root_shared_x,
        _column_x_after(
            model,
            blocks,
            profile=profile,
            system=ROOT_SYSTEM,
            column_block_ids=sources,
            start_x=profile.root_source_x,
        ),
    )
    for layer in sorted(shared_by_layer):
        layer_block_ids = _sort_blocks(shared_by_layer[layer], blocks)
        _stack_column(model, blocks, profile=profile, system=ROOT_SYSTEM, block_ids=layer_block_ids, x=next_x, base_y=40)
        next_x = _column_x_after(
            model,
            blocks,
            profile=profile,
            system=ROOT_SYSTEM,
            column_block_ids=layer_block_ids,
            start_x=next_x,
        )

    subsystem_x = max(
        profile.root_subsystem_x,
        next_x
        if shared_by_layer
        else _column_x_after(
            model,
            blocks,
            profile=profile,
            system=ROOT_SYSTEM,
            column_block_ids=sources,
            start_x=profile.root_source_x,
        ),
    )
    subsystem_y = 40
    for index, block_id in enumerate(subsystems):
        port_count = max(
            int(blocks[block_id]["metadata"].get("inport_count", 1)),
            int(blocks[block_id]["metadata"].get("outport_count", 1)),
            1,
        )
        width = _block_width(blocks[block_id], profile)
        height = max(_block_height(blocks[block_id], profile), 40 + port_count * profile.scaled_port_row_gap())
        blocks[block_id]["position"] = _position(
            subsystem_x,
            subsystem_y,
            width=width,
            height=height,
        )
        subsystem_y += height + profile.scaled_port_row_gap()

    output_x = max(
        profile.root_outport_x,
        _column_x_after(
            model,
            blocks,
            profile=profile,
            system=ROOT_SYSTEM,
            column_block_ids=subsystems,
            start_x=subsystem_x,
        ),
    )
    _stack_column(model, blocks, profile=profile, system=ROOT_SYSTEM, block_ids=outputs, x=output_x, base_y=60)


def _assign_subsystem_layout(model: BackendSimulinkModelDict, subsystem_id: str, profile: LayoutProfile) -> None:
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

    _stack_column(
        model,
        blocks,
        profile=profile,
        system=subsystem_id,
        block_ids=inports,
        x=profile.subsystem_inport_x,
        base_y=40,
    )

    compute_by_layer: dict[int, list[str]] = {}
    for block_id in compute:
        layer = int(blocks[block_id]["metadata"].get("layer_hint", 0))
        compute_by_layer.setdefault(layer, []).append(block_id)
    next_x = max(
        profile.subsystem_compute_x,
        _column_x_after(
            model,
            blocks,
            profile=profile,
            system=subsystem_id,
            column_block_ids=inports,
            start_x=profile.subsystem_inport_x,
        ),
    )
    for layer in sorted(compute_by_layer):
        layer_block_ids = _sort_blocks(compute_by_layer[layer], blocks)
        _stack_column(
            model,
            blocks,
            profile=profile,
            system=subsystem_id,
            block_ids=layer_block_ids,
            x=next_x,
            base_y=40,
        )
        next_x = _column_x_after(
            model,
            blocks,
            profile=profile,
            system=subsystem_id,
            column_block_ids=layer_block_ids,
            start_x=next_x,
        )

    integrator_x = max(
        profile.subsystem_integrator_x if not compute else next_x,
        _column_x_after(
            model,
            blocks,
            profile=profile,
            system=subsystem_id,
            column_block_ids=inports if not compute else [],
            start_x=profile.subsystem_inport_x,
        )
        if not compute
        else next_x,
    )
    _stack_column(
        model,
        blocks,
        profile=profile,
        system=subsystem_id,
        block_ids=integrators,
        x=integrator_x,
        base_y=40,
    )

    outport_x = max(
        profile.subsystem_outport_x,
        _column_x_after(
            model,
            blocks,
            profile=profile,
            system=subsystem_id,
            column_block_ids=integrators,
            start_x=integrator_x,
        ),
    )
    _stack_column(
        model,
        blocks,
        profile=profile,
        system=subsystem_id,
        block_ids=outports,
        x=outport_x,
        base_y=40,
    )


def _column_groups(
    model: BackendSimulinkModelDict,
    *,
    system: str,
) -> list[tuple[int, list[str]]]:
    grouped: dict[int, list[str]] = {}
    for block_id, spec in model["blocks"].items():
        if spec["system"] != system:
            continue
        position = spec.get("position")
        if position is None:
            continue
        grouped.setdefault(int(position[0]), []).append(block_id)
    return [
        (x, sorted(block_ids, key=lambda block_id: (int(model["blocks"][block_id]["position"][1]), block_id)))
        for x, block_ids in sorted(grouped.items())
    ]


def _skip_refinement_for_column(
    blocks: dict[str, dict[str, object]],
    block_ids: list[str],
) -> bool:
    return any(blocks[block_id]["type"] in {"Inport", "Outport", "Integrator"} for block_id in block_ids)


def _refinement_target_y(
    model: BackendSimulinkModelDict,
    *,
    system: str,
    block_id: str,
) -> float:
    blocks = model["blocks"]
    position = blocks[block_id].get("position")
    if position is None:
        return 0.0
    current_y = _center_y(position)
    contributions: list[float] = []
    for connection in model["connections"]:
        if connection["system"] != system:
            continue
        neighbor_id: str | None = None
        if connection["src_block"] == block_id:
            neighbor_id = str(connection["dst_block"])
        elif connection["dst_block"] == block_id:
            neighbor_id = str(connection["src_block"])
        if neighbor_id is None:
            continue
        neighbor_position = blocks[neighbor_id].get("position")
        if neighbor_position is None:
            continue
        weight = 2 if abs(int(neighbor_position[0]) - int(position[0])) <= 2 * LAYER_X_SPACING else 1
        contributions.extend([_center_y(neighbor_position)] * weight)
    if not contributions:
        return current_y
    return sum(contributions) / len(contributions)


def _refine_system_layout(
    model: BackendSimulinkModelDict,
    *,
    system: str,
    profile: LayoutProfile,
) -> None:
    blocks = model["blocks"]
    if profile.refinement_passes <= 0:
        return
    for _ in range(profile.refinement_passes):
        columns = _column_groups(model, system=system)
        updated = False
        for x, block_ids in columns:
            if len(block_ids) <= 1 or _skip_refinement_for_column(blocks, block_ids):
                continue
            current_order = list(block_ids)
            refined_order = sorted(
                current_order,
                key=lambda block_id: (
                    _refinement_target_y(model, system=system, block_id=block_id),
                    _center_y(blocks[block_id]["position"]),
                    str(blocks[block_id].get("name", block_id)),
                    block_id,
                ),
            )
            if refined_order == current_order:
                continue
            _stack_column(
                model,
                blocks,
                profile=profile,
                system=system,
                block_ids=refined_order,
                x=x,
                base_y=int(min(blocks[block_id]["position"][1] for block_id in current_order)),
            )
            updated = True
        if not updated:
            return


def _rect_from_position(position: list[int]) -> Rect:
    return (int(position[0]), int(position[1]), int(position[2]), int(position[3]))


def _rect_clearance(a: Rect, b: Rect) -> int:
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    if dx == 0 and dy == 0:
        return -1
    if dx == 0:
        return dy
    if dy == 0:
        return dx
    return min(dx, dy)


def _label_rect(
    model: BackendSimulinkModelDict,
    connection: dict[str, object],
    profile: LayoutProfile,
) -> Rect | None:
    label = str(connection.get("label", "")).strip()
    if not label:
        return None
    blocks = model["blocks"]
    src_position = blocks[connection["src_block"]].get("position")
    dst_position = blocks[connection["dst_block"]].get("position")
    if src_position is None or dst_position is None:
        return None
    src_rect = _rect_from_position(src_position)
    dst_rect = _rect_from_position(dst_position)
    mid_x = (src_rect[2] + dst_rect[0]) // 2
    mid_y = ((src_rect[1] + src_rect[3]) // 2 + (dst_rect[1] + dst_rect[3]) // 2) // 2
    width = _estimated_text_width(label, profile) + profile.text_padding_x
    height = _estimated_text_lines(label, profile) * profile.trace_line_height
    half_width = max(1, width // 2)
    half_height = max(1, height // 2)
    return (mid_x - half_width, mid_y - half_height, mid_x + half_width, mid_y + half_height)


def audit_layout(
    model: BackendSimulinkModelDict,
    *,
    profile: LayoutProfile | None = None,
    iterations: int = 1,
) -> LayoutQualityReport:
    active_profile = profile or LayoutProfile()
    blocks = model["blocks"]
    block_rects_by_system: dict[str, list[tuple[str, Rect]]] = {}
    for block_id, spec in blocks.items():
        position = spec.get("position")
        if position is None:
            continue
        block_rects_by_system.setdefault(spec["system"], []).append((block_id, _rect_from_position(position)))

    min_block_clearance: int | None = None
    block_overlap_count = 0
    for system_rects in block_rects_by_system.values():
        for (_, left_rect), (_, right_rect) in combinations(system_rects, 2):
            clearance = _rect_clearance(left_rect, right_rect)
            if clearance < 0:
                block_overlap_count += 1
            elif min_block_clearance is None or clearance < min_block_clearance:
                min_block_clearance = clearance

    label_rects_by_system: dict[str, list[Rect]] = {}
    label_block_overlap_count = 0
    min_label_block_clearance: int | None = None
    for connection in model["connections"]:
        rect = _label_rect(model, connection, active_profile)
        if rect is None:
            continue
        system = str(connection["system"])
        label_rects_by_system.setdefault(system, []).append(rect)
        for _, block_rect in block_rects_by_system.get(system, []):
            clearance = _rect_clearance(rect, block_rect)
            if clearance < 0:
                label_block_overlap_count += 1
            elif min_label_block_clearance is None or clearance < min_label_block_clearance:
                min_label_block_clearance = clearance

    label_label_overlap_count = 0
    min_label_label_clearance: int | None = None
    for label_rects in label_rects_by_system.values():
        for left_rect, right_rect in combinations(label_rects, 2):
            clearance = _rect_clearance(left_rect, right_rect)
            if clearance < 0:
                label_label_overlap_count += 1
            elif min_label_label_clearance is None or clearance < min_label_label_clearance:
                min_label_label_clearance = clearance

    return LayoutQualityReport(
        block_overlap_count=block_overlap_count,
        label_block_overlap_count=label_block_overlap_count,
        label_label_overlap_count=label_label_overlap_count,
        min_block_clearance=min_block_clearance,
        min_label_block_clearance=min_label_block_clearance,
        min_label_label_clearance=min_label_label_clearance,
        iterations=iterations,
        profile=active_profile,
    )


def _repair_profile(profile: LayoutProfile, report: LayoutQualityReport) -> LayoutProfile:
    horizontal_scale = profile.horizontal_scale
    vertical_scale = profile.vertical_scale

    if report.block_overlap_count or report.min_block_clearance is not None and report.min_block_clearance < MIN_BLOCK_CLEARANCE_TARGET:
        horizontal_scale *= 1.2
        vertical_scale *= 1.15
    if report.label_block_overlap_count or (
        report.min_label_block_clearance is not None
        and report.min_label_block_clearance < MIN_LABEL_BLOCK_CLEARANCE_TARGET
    ):
        horizontal_scale *= 1.25
        vertical_scale *= 1.1
    if report.label_label_overlap_count or (
        report.min_label_label_clearance is not None
        and report.min_label_label_clearance < MIN_LABEL_LABEL_CLEARANCE_TARGET
    ):
        horizontal_scale *= 1.1
        vertical_scale *= 1.2

    return replace(
        profile,
        horizontal_scale=min(horizontal_scale, 4.0),
        vertical_scale=min(vertical_scale, 4.0),
    )


def _apply_layout_with_profile(
    model: BackendSimulinkModelDict,
    profile: LayoutProfile,
    *,
    refine_columns: bool,
) -> BackendSimulinkModelDict:
    laid_out = deepcopy(model)
    _assign_root_layout(laid_out, profile)
    subsystem_ids = [
        block_id
        for block_id, spec in laid_out["blocks"].items()
        if spec["system"] == ROOT_SYSTEM and spec["type"] == "Subsystem"
    ]
    for subsystem_id in sorted(subsystem_ids, key=lambda block_id: str(laid_out["blocks"][block_id]["name"])):
        _assign_subsystem_layout(laid_out, subsystem_id, profile)
    if refine_columns:
        _refine_system_layout(laid_out, system=ROOT_SYSTEM, profile=profile)
        for subsystem_id in sorted(subsystem_ids):
            _refine_system_layout(laid_out, system=subsystem_id, profile=profile)
    return laid_out


def apply_legacy_layout(
    model: BackendSimulinkModelDict,
    *,
    profile: LayoutProfile | None = None,
    max_iterations: int = MAX_LAYOUT_REPAIR_ITERATIONS,
) -> BackendSimulinkModelDict:
    """Apply the original readable-backend placement strategy without refinement sweeps."""
    active_profile = profile or LayoutProfile(refinement_passes=0)
    best_model: BackendSimulinkModelDict | None = None
    best_report: LayoutQualityReport | None = None

    for iteration in range(1, max_iterations + 1):
        laid_out = _apply_layout_with_profile(model, active_profile, refine_columns=False)
        report = audit_layout(laid_out, profile=active_profile, iterations=iteration)
        laid_out.setdefault("metadata", {})
        laid_out["metadata"]["layout_quality"] = report.to_metadata()
        laid_out["metadata"]["layout_strategy"] = "legacy"
        if best_report is None or report.score > best_report.score:
            best_model = laid_out
            best_report = report
        if report.passes:
            return laid_out
        next_profile = _repair_profile(active_profile, report)
        if next_profile == active_profile:
            break
        active_profile = next_profile

    if best_model is None:
        best_model = _apply_layout_with_profile(model, active_profile, refine_columns=False)
        best_model.setdefault("metadata", {})
        best_model["metadata"]["layout_quality"] = audit_layout(
            best_model,
            profile=active_profile,
            iterations=0,
        ).to_metadata()
        best_model["metadata"]["layout_strategy"] = "legacy"
    return best_model


def apply_deterministic_layout(
    model: BackendSimulinkModelDict,
    *,
    profile: LayoutProfile | None = None,
    max_iterations: int = MAX_LAYOUT_REPAIR_ITERATIONS,
) -> BackendSimulinkModelDict:
    """Assign deterministic positions, then repair spacing until layout quality thresholds pass."""
    active_profile = profile or LayoutProfile()
    best_model: BackendSimulinkModelDict | None = None
    best_report: LayoutQualityReport | None = None

    for iteration in range(1, max_iterations + 1):
        laid_out = _apply_layout_with_profile(model, active_profile, refine_columns=True)
        report = audit_layout(laid_out, profile=active_profile, iterations=iteration)
        laid_out.setdefault("metadata", {})
        laid_out["metadata"]["layout_quality"] = report.to_metadata()
        laid_out["metadata"]["layout_strategy"] = "deterministic"
        if best_report is None or report.score > best_report.score:
            best_model = laid_out
            best_report = report
        if report.passes:
            return laid_out
        next_profile = _repair_profile(active_profile, report)
        if next_profile == active_profile:
            break
        active_profile = next_profile

    if best_model is None:
        best_model = _apply_layout_with_profile(model, active_profile, refine_columns=True)
        best_model.setdefault("metadata", {})
        best_model["metadata"]["layout_quality"] = audit_layout(
            best_model,
            profile=active_profile,
            iterations=0,
        ).to_metadata()
        best_model["metadata"]["layout_strategy"] = "deterministic"
    return best_model


def annotate_integrator_orders(model: BackendSimulinkModelDict) -> None:
    """Attach derivative-order hints to integrators for vertical chain layout."""
    for block_spec in model["blocks"].values():
        if block_spec["type"] != "Integrator":
            continue
        metadata = block_spec.setdefault("metadata", {})
        state = str(metadata.get("state", ""))
        metadata["state_order"] = state_order(state) if state else 0
