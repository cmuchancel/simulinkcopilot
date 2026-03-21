from __future__ import annotations

import numpy as np

from eqn2sim_gui.preview import (
    render_equation_preview,
    render_state_trajectory_comparison_preview,
    render_state_trajectory_preview,
)


def test_render_equation_preview_returns_none_for_blank_input() -> None:
    result = render_equation_preview(" \n\n ")
    assert result.svg is None
    assert result.error is None


def test_render_equation_preview_renders_svg() -> None:
    result = render_equation_preview("\\dot{x} = -ax\nx = 1")
    assert result.error is None
    assert result.svg is not None
    assert "<svg" in result.svg


def test_render_state_trajectory_preview_returns_none_when_data_missing() -> None:
    result = render_state_trajectory_preview({})
    assert result.svg is None
    assert result.error is None


def test_render_state_trajectory_preview_renders_svg() -> None:
    result = render_state_trajectory_preview(
        {
            "state_names": ["x", "x_dot"],
            "t": np.array([0.0, 1.0, 2.0]),
            "states": np.array([[0.0, 0.0], [1.0, 0.5], [1.5, 0.25]]),
        }
    )
    assert result.error is None
    assert result.svg is not None
    assert "<svg" in result.svg


def test_render_state_trajectory_comparison_preview_returns_none_for_empty_input() -> None:
    result = render_state_trajectory_comparison_preview([])
    assert result.svg is None
    assert result.error is None


def test_render_state_trajectory_comparison_preview_detects_state_mismatch() -> None:
    result = render_state_trajectory_comparison_preview(
        [
            (
                "ODE",
                {
                    "state_names": ["x"],
                    "t": np.array([0.0, 1.0]),
                    "states": np.array([[0.0], [1.0]]),
                },
                "-",
            ),
            (
                "Simulink",
                {
                    "state_names": ["theta"],
                    "t": np.array([0.0, 1.0]),
                    "states": np.array([[0.0], [1.0]]),
                },
                "--",
            ),
        ]
    )
    assert result.svg is None
    assert "same state ordering" in result.error


def test_render_state_trajectory_comparison_preview_renders_overlay_svg() -> None:
    result = render_state_trajectory_comparison_preview(
        [
            (
                "ODE",
                {
                    "state_names": ["x"],
                    "t": np.array([0.0, 1.0]),
                    "states": np.array([[0.0], [1.0]]),
                },
                "-",
            ),
            (
                "Simulink",
                {
                    "state_names": ["x"],
                    "t": np.array([0.0, 1.0]),
                    "states": np.array([[0.0], [1.1]]),
                },
                "--",
            ),
        ]
    )
    assert result.error is None
    assert result.svg is not None
    assert "<svg" in result.svg
