"""Local equation-preview rendering helpers for the Eqn2Sim GUI."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import math
import os
from pathlib import Path
import tempfile

_MPLCONFIGDIR = Path(tempfile.gettempdir()) / "simulinkcopilot_mplconfig"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))
_XDG_CACHE_HOME = Path(tempfile.gettempdir()) / "simulinkcopilot_cache"
_XDG_CACHE_HOME.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(_XDG_CACHE_HOME))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class PreviewRenderResult:
    """Rendered equation preview payload."""

    svg: str | None
    error: str | None = None


def render_equation_preview(latex: str) -> PreviewRenderResult:
    """Render a local SVG preview for one or more equations."""
    lines = [line.strip() for line in latex.splitlines() if line.strip()]
    if not lines:
        return PreviewRenderResult(svg=None, error=None)

    figure, axes = plt.subplots(len(lines), 1, figsize=(11, max(1.8, 1.4 * len(lines))), squeeze=False)
    try:
        for row, line in enumerate(lines):
            axis = axes[row][0]
            axis.axis("off")
            axis.text(
                0.02,
                0.5,
                f"${line}$",
                fontsize=18,
                ha="left",
                va="center",
            )
        figure.tight_layout()
        buffer = StringIO()
        figure.savefig(buffer, format="svg", bbox_inches="tight")
        return PreviewRenderResult(svg=buffer.getvalue(), error=None)
    except Exception as exc:  # pragma: no cover - depends on local matplotlib mathtext support
        return PreviewRenderResult(svg=None, error=f"Preview rendering failed: {exc}")
    finally:
        plt.close(figure)


def render_state_trajectory_preview(
    simulation_result: dict[str, object],
    *,
    series_label: str = "ODE preview",
) -> PreviewRenderResult:
    """Render state trajectories over time as an SVG preview."""
    state_names = list(simulation_result.get("state_names", []))
    time_values = simulation_result.get("t")
    state_values = simulation_result.get("states")
    if not state_names or time_values is None or state_values is None:
        return PreviewRenderResult(svg=None, error=None)

    state_count = len(state_names)
    columns = 1 if state_count <= 2 else 2
    rows = math.ceil(state_count / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(11, max(3.0, 3.2 * rows)), squeeze=False)

    try:
        for index, state_name in enumerate(state_names):
            axis = axes[index // columns][index % columns]
            axis.plot(time_values, state_values[:, index], linewidth=1.7, color="#0f766e", label=series_label)
            axis.set_title(state_name)
            axis.set_xlabel("time")
            axis.grid(True, alpha=0.3)
            axis.legend()

        for index in range(state_count, rows * columns):
            axes[index // columns][index % columns].axis("off")

        figure.tight_layout()
        buffer = StringIO()
        figure.savefig(buffer, format="svg", bbox_inches="tight")
        return PreviewRenderResult(svg=buffer.getvalue(), error=None)
    except Exception as exc:  # pragma: no cover - depends on local matplotlib runtime
        return PreviewRenderResult(svg=None, error=f"Trajectory plot rendering failed: {exc}")
    finally:
        plt.close(figure)


def render_state_trajectory_comparison_preview(
    series_results: list[tuple[str, dict[str, object], str]],
) -> PreviewRenderResult:
    """Render overlaid state trajectories for multiple simulation series."""
    if not series_results:
        return PreviewRenderResult(svg=None, error=None)

    reference_names = list(series_results[0][1].get("state_names", []))
    if not reference_names:
        return PreviewRenderResult(svg=None, error=None)

    state_count = len(reference_names)
    columns = 1 if state_count <= 2 else 2
    rows = math.ceil(state_count / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(11, max(3.0, 3.2 * rows)), squeeze=False)

    try:
        for index, state_name in enumerate(reference_names):
            axis = axes[index // columns][index % columns]
            for label, result, style in series_results:
                state_names = list(result.get("state_names", []))
                if state_names != reference_names:
                    raise ValueError("Trajectory series do not share the same state ordering.")
                axis.plot(
                    result.get("t"),
                    result.get("states")[:, index],
                    style,
                    linewidth=1.7,
                    label=label,
                )
            axis.set_title(state_name)
            axis.set_xlabel("time")
            axis.grid(True, alpha=0.3)
            axis.legend()

        for index in range(state_count, rows * columns):
            axes[index // columns][index % columns].axis("off")

        figure.tight_layout()
        buffer = StringIO()
        figure.savefig(buffer, format="svg", bbox_inches="tight")
        return PreviewRenderResult(svg=buffer.getvalue(), error=None)
    except Exception as exc:  # pragma: no cover - depends on local matplotlib runtime
        return PreviewRenderResult(svg=None, error=f"Trajectory plot rendering failed: {exc}")
    finally:
        plt.close(figure)
