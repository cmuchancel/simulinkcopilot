"""Deterministic local renderer for backend Simulink layout dictionaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from backend.layout_metrics import connection_polyline
from backend.simulink_dict import ROOT_SYSTEM, BackendSimulinkModelDict
from simulink.utils import sanitize_block_name


@dataclass(frozen=True)
class RenderedSystemImage:
    system: str
    path: str
    width: int
    height: int


def _system_bounds(model: BackendSimulinkModelDict, system: str) -> tuple[int, int, int, int] | None:
    rects = [
        tuple(int(value) for value in spec["position"])
        for spec in model["blocks"].values()
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


def _block_facecolor(block_type: str) -> str:
    return {
        "Subsystem": "#dceeff",
        "Integrator": "#fff1d6",
        "Inport": "#e6f4ea",
        "Outport": "#f7e6ef",
        "Sum": "#eef1ff",
        "Gain": "#f1efff",
        "Product": "#f7f3eb",
        "Divide": "#f7f3eb",
    }.get(block_type, "#f7f7f7")


def render_system_image(
    model: BackendSimulinkModelDict,
    *,
    system: str = ROOT_SYSTEM,
    output_path: str | Path,
    title: str | None = None,
) -> RenderedSystemImage:
    """Render one system from a model dict to a local PNG image."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    bounds = _system_bounds(model, system)
    if bounds is None:
        fig, ax = plt.subplots(figsize=(6, 2.5))
        ax.text(0.5, 0.5, f"{system}: no positioned blocks", ha="center", va="center")
        ax.axis("off")
        fig.savefig(output, dpi=140, bbox_inches="tight")
        plt.close(fig)
        return RenderedSystemImage(system=system, path=str(output), width=0, height=0)

    left, top, right, bottom = bounds
    margin = 60
    width = max(1, right - left)
    height = max(1, bottom - top)
    fig, ax = plt.subplots(figsize=(max(8.0, width / 110.0), max(3.5, height / 110.0)))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    # Draw connections first.
    for connection in model["connections"]:
        if connection["system"] != system:
            continue
        polyline = connection_polyline(model, connection)
        if len(polyline) < 2:
            continue
        xs = [point[0] for point in polyline]
        ys = [point[1] for point in polyline]
        ax.plot(xs, ys, color="#2b5fab", linewidth=1.6, zorder=1)
        label = str(connection.get("label", "")).strip()
        if label:
            midpoint = polyline[len(polyline) // 2]
            ax.text(
                midpoint[0],
                midpoint[1] - 8,
                label,
                fontsize=8,
                color="#23436f",
                ha="center",
                va="bottom",
                zorder=2,
                bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.9},
            )

    for block_id, block_spec in model["blocks"].items():
        if block_spec["system"] != system or block_spec.get("position") is None:
            continue
        block_type = str(block_spec["type"])
        position = [int(value) for value in block_spec["position"]]
        block_left, block_top, block_right, block_bottom = position
        block_width = block_right - block_left
        block_height = block_bottom - block_top
        label = str(block_spec.get("name", block_id))
        patch_kwargs = {
            "linewidth": 1.4,
            "edgecolor": "#3a3a3a",
            "facecolor": _block_facecolor(block_type),
            "zorder": 3,
        }
        if block_type in {"Inport", "Outport"}:
            patch = FancyBboxPatch(
                (block_left, block_top),
                block_width,
                block_height,
                boxstyle="round,pad=0.02,rounding_size=8",
                **patch_kwargs,
            )
        else:
            patch = Rectangle((block_left, block_top), block_width, block_height, **patch_kwargs)
        ax.add_patch(patch)
        ax.text(
            block_left + block_width / 2.0,
            block_top + block_height / 2.0,
            label,
            ha="center",
            va="center",
            fontsize=8.5,
            color="#202020",
            zorder=4,
        )
        if block_type == "Integrator":
            ax.text(
                block_left + block_width / 2.0,
                block_top + block_height * 0.22,
                "1/s",
                ha="center",
                va="center",
                fontsize=9,
                color="#6a4b00",
                zorder=4,
            )

    ax.set_xlim(left - margin, right + margin)
    ax.set_ylim(bottom + margin, top - margin)
    ax.axis("off")
    ax.set_title(title or sanitize_block_name(system), fontsize=11, color="#202020")
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return RenderedSystemImage(system=system, path=str(output), width=width, height=height)
