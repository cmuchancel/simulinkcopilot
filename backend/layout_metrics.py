"""Higher-level readability metrics for laid-out Simulink model dictionaries."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import ceil

from backend.layout import LayoutProfile, audit_layout
from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict
from backend.traceability import state_base_name


Rect = tuple[int, int, int, int]
Point = tuple[float, float]
Segment = tuple[Point, Point]

PAGE_WIDTH_UNITS = 1160
PAGE_HEIGHT_UNITS = 820
FEEDBACK_ROUTE_MARGIN = 60


@dataclass(frozen=True)
class LayoutMetrics:
    block_overlap_count: int
    label_block_overlap_count: int
    label_label_overlap_count: int
    connection_crossing_count: int
    block_line_crossing_count: int
    reverse_flow_edge_count: int
    bend_count: int
    alignment_score: float
    integrator_chain_score: float
    feedback_clarity_score: float
    subsystem_balance_score: float
    canvas_width: int
    canvas_height: int
    estimated_page_count: int
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "block_overlap_count": self.block_overlap_count,
            "label_block_overlap_count": self.label_block_overlap_count,
            "label_label_overlap_count": self.label_label_overlap_count,
            "connection_crossing_count": self.connection_crossing_count,
            "block_line_crossing_count": self.block_line_crossing_count,
            "reverse_flow_edge_count": self.reverse_flow_edge_count,
            "bend_count": self.bend_count,
            "alignment_score": round(self.alignment_score, 2),
            "integrator_chain_score": round(self.integrator_chain_score, 2),
            "feedback_clarity_score": round(self.feedback_clarity_score, 2),
            "subsystem_balance_score": round(self.subsystem_balance_score, 2),
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "estimated_page_count": self.estimated_page_count,
            "score": round(self.score, 2),
        }


def _rect_from_position(position: list[int]) -> Rect:
    return (int(position[0]), int(position[1]), int(position[2]), int(position[3]))


def _center(position: list[int]) -> Point:
    return ((int(position[0]) + int(position[2])) / 2.0, (int(position[1]) + int(position[3])) / 2.0)


def _system_block_ids(model: BackendSimulinkModelDict, system: str) -> list[str]:
    return [block_id for block_id, spec in model["blocks"].items() if spec["system"] == system]


def _system_bounds(model: BackendSimulinkModelDict, system: str) -> Rect | None:
    rects = [
        _rect_from_position(spec["position"])
        for block_id, spec in model["blocks"].items()
        if spec["system"] == system and spec.get("position") is not None
    ]
    if not rects:
        return None
    return (
        min(rect[0] for rect in rects),
        min(rect[1] for rect in rects),
        max(rect[2] for rect in rects),
        max(rect[3] for rect in rects),
    )


def _alignment_group_key(block_spec: dict[str, object]) -> tuple[str, int]:
    metadata = block_spec.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    block_type = str(block_spec["type"])
    role = str(metadata.get("layout_role", block_type))
    layer_hint = int(metadata.get("layer_hint", 0))
    if role == "compute":
        return (role, layer_hint)
    if role == "shared":
        return (role, layer_hint)
    if role == "subsystem":
        return (role, 0)
    if block_type == "Subsystem":
        return ("subsystem", 0)
    return (role or block_type, 0)


def _horizontal_segments(points: list[Point]) -> list[Segment]:
    return [segment for segment in zip(points, points[1:]) if segment[0] != segment[1]]


def connection_polyline(
    model: BackendSimulinkModelDict,
    connection: dict[str, object],
    *,
    route_margin: int = FEEDBACK_ROUTE_MARGIN,
) -> list[Point]:
    """Return a deterministic orthogonal route proxy for a connection."""
    blocks = model["blocks"]
    src_position = blocks[connection["src_block"]].get("position")
    dst_position = blocks[connection["dst_block"]].get("position")
    if src_position is None or dst_position is None:
        return []
    src_rect = _rect_from_position(src_position)
    dst_rect = _rect_from_position(dst_position)
    src_center_x, src_center_y = _center(src_position)
    dst_center_x, dst_center_y = _center(dst_position)

    if src_center_x <= dst_center_x:
        start = (src_rect[2], src_center_y)
        end = (dst_rect[0], dst_center_y)
        mid_x = (start[0] + end[0]) / 2.0
        if abs(start[1] - end[1]) < 1e-6:
            return [start, end]
        return [start, (mid_x, start[1]), (mid_x, end[1]), end]

    start = (src_rect[0], src_center_y)
    lane_y = min(src_rect[1], dst_rect[1]) - route_margin
    lane_x = dst_rect[0] - route_margin
    end = (dst_rect[0], dst_center_y)
    return [
        start,
        (start[0] - route_margin / 2.0, start[1]),
        (start[0] - route_margin / 2.0, lane_y),
        (lane_x, lane_y),
        (lane_x, end[1]),
        end,
    ]


def _segment_orientation(segment: Segment) -> str:
    (x1, y1), (x2, y2) = segment
    if abs(y1 - y2) < 1e-6:
        return "horizontal"
    if abs(x1 - x2) < 1e-6:
        return "vertical"
    return "diagonal"


def _segments_intersect(left: Segment, right: Segment) -> bool:
    left_kind = _segment_orientation(left)
    right_kind = _segment_orientation(right)
    if left_kind == "diagonal" or right_kind == "diagonal":
        return False
    if left_kind == right_kind == "horizontal":
        y = left[0][1]
        if abs(y - right[0][1]) >= 1e-6:
            return False
        left_min, left_max = sorted((left[0][0], left[1][0]))
        right_min, right_max = sorted((right[0][0], right[1][0]))
        return max(left_min, right_min) < min(left_max, right_max)
    if left_kind == right_kind == "vertical":
        x = left[0][0]
        if abs(x - right[0][0]) >= 1e-6:
            return False
        left_min, left_max = sorted((left[0][1], left[1][1]))
        right_min, right_max = sorted((right[0][1], right[1][1]))
        return max(left_min, right_min) < min(left_max, right_max)
    if left_kind == "horizontal":
        horizontal, vertical = left, right
    else:
        horizontal, vertical = right, left
    y = horizontal[0][1]
    x = vertical[0][0]
    x_min, x_max = sorted((horizontal[0][0], horizontal[1][0]))
    y_min, y_max = sorted((vertical[0][1], vertical[1][1]))
    return x_min < x < x_max and y_min < y < y_max


def _segment_crosses_rect(segment: Segment, rect: Rect) -> bool:
    x1, y1 = segment[0]
    x2, y2 = segment[1]
    left, top, right, bottom = rect
    if abs(y1 - y2) < 1e-6:
        y = y1
        if not (top < y < bottom):
            return False
        x_min, x_max = sorted((x1, x2))
        return x_min < right and x_max > left
    if abs(x1 - x2) < 1e-6:
        x = x1
        if not (left < x < right):
            return False
        y_min, y_max = sorted((y1, y2))
        return y_min < bottom and y_max > top
    return False


def _alignment_score(model: BackendSimulinkModelDict) -> float:
    deviations: list[float] = []
    grouped: dict[tuple[str, tuple[str, int]], list[int]] = {}
    for block_id, block_spec in model["blocks"].items():
        position = block_spec.get("position")
        if position is None:
            continue
        grouped.setdefault((str(block_spec["system"]), _alignment_group_key(block_spec)), []).append(int(position[0]))
    for positions in grouped.values():
        if len(positions) <= 1:
            continue
        target = sorted(positions)[len(positions) // 2]
        deviations.extend(abs(position - target) for position in positions)
    if not deviations:
        return 100.0
    return max(0.0, 100.0 - sum(deviations) / len(deviations))


def _integrator_chain_score(model: BackendSimulinkModelDict) -> float:
    grouped: dict[tuple[str, str], list[tuple[int, list[int]]]] = {}
    for block_spec in model["blocks"].values():
        if block_spec["type"] != "Integrator" or block_spec.get("position") is None:
            continue
        metadata = block_spec.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        state = str(metadata.get("state", ""))
        grouped.setdefault((str(block_spec["system"]), state_base_name(state)), []).append(
            (int(metadata.get("state_order", 0)), block_spec["position"])
        )
    if not grouped:
        return 100.0
    total = 0.0
    for entries in grouped.values():
        entries.sort(key=lambda item: -item[0])
        x_positions = [int(position[0]) for _, position in entries]
        y_positions = [int(position[1]) for _, position in entries]
        x_penalty = max(x_positions) - min(x_positions)
        order_penalty = 0.0
        if len(y_positions) > 1:
            for first, second in zip(y_positions, y_positions[1:]):
                if first >= second:
                    order_penalty += abs(first - second) + 20
        total += max(0.0, 100.0 - x_penalty - order_penalty)
    return total / len(grouped)


def _feedback_clarity_score(model: BackendSimulinkModelDict) -> float:
    blocks = model["blocks"]
    clarity_samples: list[float] = []
    for connection in model["connections"]:
        points = connection_polyline(model, connection)
        if len(points) < 2:
            continue
        src_position = blocks[connection["src_block"]].get("position")
        dst_position = blocks[connection["dst_block"]].get("position")
        if src_position is None or dst_position is None:
            continue
        if _center(src_position)[0] <= _center(dst_position)[0]:
            continue
        route_segments = _horizontal_segments(points)
        blockers = 0
        for block_id, block_spec in blocks.items():
            if block_id in {connection["src_block"], connection["dst_block"]}:
                continue
            rect_position = block_spec.get("position")
            if rect_position is None or block_spec["system"] != connection["system"]:
                continue
            rect = _rect_from_position(rect_position)
            if any(_segment_crosses_rect(segment, rect) for segment in route_segments):
                blockers += 1
        clarity_samples.append(max(0.0, 100.0 - 20.0 * blockers))
    if not clarity_samples:
        return 100.0
    return sum(clarity_samples) / len(clarity_samples)


def _subsystem_balance_score(model: BackendSimulinkModelDict) -> float:
    scores: list[float] = []
    for block_id, block_spec in model["blocks"].items():
        if block_spec["type"] != "Subsystem" or block_spec.get("position") is None:
            continue
        child_bounds = _system_bounds(model, block_id)
        if child_bounds is None:
            scores.append(100.0)
            continue
        subsystem_rect = _rect_from_position(block_spec["position"])
        child_width = max(1, child_bounds[2] - child_bounds[0])
        child_height = max(1, child_bounds[3] - child_bounds[1])
        outer_width = max(1, subsystem_rect[2] - subsystem_rect[0])
        outer_height = max(1, subsystem_rect[3] - subsystem_rect[1])
        width_ratio = min(1.0, child_width / outer_width)
        height_ratio = min(1.0, child_height / outer_height)
        scores.append(50.0 * (width_ratio + height_ratio))
    if not scores:
        return 100.0
    return sum(scores) / len(scores)


def _canvas_size(model: BackendSimulinkModelDict) -> tuple[int, int]:
    bounds = _system_bounds(model, ROOT_SYSTEM)
    if bounds is None:
        return (0, 0)
    return (bounds[2] - bounds[0], bounds[3] - bounds[1])


def measure_layout(
    model: BackendSimulinkModelDict,
    *,
    profile: LayoutProfile | None = None,
) -> LayoutMetrics:
    """Compute richer readability metrics than the basic overlap audit alone."""
    audit = audit_layout(model, profile=profile)
    connection_crossing_count = 0
    block_line_crossing_count = 0
    reverse_flow_edge_count = 0
    bend_count = 0

    by_system: dict[str, list[tuple[dict[str, object], list[Segment]]]] = {}
    for connection in model["connections"]:
        points = connection_polyline(model, connection)
        if len(points) < 2:
            continue
        bend_count += max(0, len(points) - 2)
        segments = _horizontal_segments(points)
        by_system.setdefault(str(connection["system"]), []).append((connection, segments))
        blocks = model["blocks"]
        src_position = blocks[connection["src_block"]].get("position")
        dst_position = blocks[connection["dst_block"]].get("position")
        if src_position is not None and dst_position is not None and _center(src_position)[0] > _center(dst_position)[0]:
            reverse_flow_edge_count += 1
        for block_id, block_spec in blocks.items():
            if block_spec["system"] != connection["system"] or block_id in {connection["src_block"], connection["dst_block"]}:
                continue
            position = block_spec.get("position")
            if position is None:
                continue
            rect = _rect_from_position(position)
            if any(_segment_crosses_rect(segment, rect) for segment in segments):
                block_line_crossing_count += 1

    for items in by_system.values():
        for (left_connection, left_segments), (right_connection, right_segments) in combinations(items, 2):
            if {
                left_connection["src_block"],
                left_connection["dst_block"],
            } & {
                right_connection["src_block"],
                right_connection["dst_block"],
            }:
                continue
            if any(_segments_intersect(left_segment, right_segment) for left_segment in left_segments for right_segment in right_segments):
                connection_crossing_count += 1

    canvas_width, canvas_height = _canvas_size(model)
    estimated_page_count = max(1, ceil(max(1, canvas_width) / PAGE_WIDTH_UNITS) * ceil(max(1, canvas_height) / PAGE_HEIGHT_UNITS))
    alignment_score = _alignment_score(model)
    integrator_chain_score = _integrator_chain_score(model)
    feedback_clarity_score = _feedback_clarity_score(model)
    subsystem_balance_score = _subsystem_balance_score(model)

    score = 100.0
    score -= audit.block_overlap_count * 30.0
    score -= audit.label_block_overlap_count * 18.0
    score -= audit.label_label_overlap_count * 10.0
    score -= connection_crossing_count * 12.0
    score -= block_line_crossing_count * 6.0
    score -= reverse_flow_edge_count * 1.5
    score -= bend_count * 0.8
    score -= max(0, estimated_page_count - 1) * 8.0
    score -= max(0.0, 100.0 - alignment_score) * 0.25
    score -= max(0.0, 100.0 - integrator_chain_score) * 0.2
    score -= max(0.0, 100.0 - feedback_clarity_score) * 0.2
    score -= max(0.0, 100.0 - subsystem_balance_score) * 0.15
    return LayoutMetrics(
        block_overlap_count=audit.block_overlap_count,
        label_block_overlap_count=audit.label_block_overlap_count,
        label_label_overlap_count=audit.label_label_overlap_count,
        connection_crossing_count=connection_crossing_count,
        block_line_crossing_count=block_line_crossing_count,
        reverse_flow_edge_count=reverse_flow_edge_count,
        bend_count=bend_count,
        alignment_score=alignment_score,
        integrator_chain_score=integrator_chain_score,
        feedback_clarity_score=feedback_clarity_score,
        subsystem_balance_score=subsystem_balance_score,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        estimated_page_count=estimated_page_count,
        score=score,
    )
